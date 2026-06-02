import time
import asyncio
from datetime import date
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
import re
from app.services.yfinance_service import analyze_stock, smart_pre_filter
from app.services.ai_service import get_ai_analysis_batch, get_cached_ai_analysis, save_ai_analysis_to_cache
from app.services.constants import get_tickers_by_index
from app.services.screen_progress import progress_manager

router = APIRouter(prefix="/api/v1/stock", tags=["Stock Screening"])

# --- SSE Progress Endpoint ---
@router.get("/progress")
async def stream_progress():
    """Server-Sent Events endpoint: stream real-time screener progress to the frontend."""
    queue = progress_manager.subscribe()

    async def event_generator():
        # Send current state immediately on connect
        current = progress_manager.current()
        yield f"data: {__import__('json').dumps(current)}\n\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {__import__('json').dumps(event)}\n\n"
                    if event.get('stage') == 'done' or event.get('stage') == 'error':
                        break
                except asyncio.TimeoutError:
                    # Heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        finally:
            progress_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

class BatchScreenRequest(BaseModel):
    tickers: list[str]

    @field_validator('tickers')
    def sanitize_tickers(cls, v):
        sanitized = []
        for t in v:
            t_clean = re.sub(r'[^a-zA-Z0-9]', '', t).upper().strip()
            if t_clean:
                sanitized.append(t_clean)
        return sanitized

def process_batch_ai(finalists: list[dict]) -> list[dict]:
    today_str = date.today().strftime('%Y-%m-%d')
    total = len(finalists)

    # 1. Cek Cache AI & Pisahkan
    cached_results = []
    tickers_to_analyze = []

    for finalist in finalists:
        ticker = finalist["ticker"]
        cached_ai = get_cached_ai_analysis(ticker, today_str)
        if cached_ai:
            combined = {**finalist, "ai_analysis": cached_ai}
            cached_results.append(combined)
        else:
            tickers_to_analyze.append(finalist)

    num_cached = len(cached_results)
    num_to_analyze = len(tickers_to_analyze)
    progress_manager.emit(
        stage="ai_cache",
        message=f"Cache check selesai: {num_cached} dari cache, {num_to_analyze} perlu dianalisis AI",
        pct=35,
        detail=f"cache={num_cached} new={num_to_analyze}"
    )

    results = []

    # 2. Chunking HANYA untuk yang belum di-cache
    chunk_size = 12
    chunks = [tickers_to_analyze[i:i + chunk_size] for i in range(0, len(tickers_to_analyze), chunk_size)]
    num_chunks = len(chunks)

    for idx, chunk in enumerate(chunks):
        chunk_tickers = [c['ticker'] for c in chunk]
        progress_manager.emit(
            stage="ai_processing",
            message=f"Gemini AI memproses batch {idx+1}/{num_chunks} ({len(chunk)} ticker)",
            pct=40 + int((idx / max(num_chunks, 1)) * 50),
            detail=f"Batch {idx+1}/{num_chunks}: {', '.join(chunk_tickers)}"
        )
        try:
            ai_batch_response = get_ai_analysis_batch(chunk)
            ai_results = ai_batch_response.get("results", [])

            # Mapping kembali berdasarkan ticker
            ai_map = {res["ticker"]: res for res in ai_results}

            for finalist in chunk:
                ticker = finalist["ticker"]
                ai_res = ai_map.get(ticker)

                if ai_res:
                    # Validasi (Satpam Cache) sebelum menyimpan
                    matriks_strategi = ai_res.get("matriks_strategi", "")
                    alasan_analisis = ai_res.get("alasan_analisis", "")

                    is_valid = (
                        matriks_strategi != "Gagal Analisis AI" and
                        not alasan_analisis.startswith("Error")
                    )

                    if is_valid:
                        # Simpan hasil baru ke cache SQLite
                        save_ai_analysis_to_cache(ai_res, today_str)
                else:
                    ai_res = {
                        "ticker": ticker,
                        "skor_akumulasi": 0.0,
                        "skor_sentimen": 1,
                        "matriks_strategi": "Gagal Analisis AI",
                        "konfirmasi_tren_mingguan": "Unknown",
                        "rekomendasi_buy": "N/A",
                        "take_profit": 0,
                        "stop_loss": 0,
                        "risk_reward_ratio": "N/A",
                        "alasan_analisis": "Error: Ticker tidak dikembalikan oleh AI"
                    }

                combined = {
                    **finalist,
                    "ai_analysis": ai_res
                }
                results.append(combined)

            progress_manager.emit(
                stage="ai_chunk_done",
                message=f"✅ Batch {idx+1}/{num_chunks} selesai",
                pct=40 + int(((idx + 1) / max(num_chunks, 1)) * 50),
                detail=f"Selesai: {', '.join(chunk_tickers)}"
            )

        except Exception as e:
            print(f"Batch AI processing error: {e}")
            for finalist in chunk:
                combined = {
                    **finalist,
                    "ai_analysis": {
                        "ticker": finalist["ticker"],
                        "skor_akumulasi": 0.0,
                        "skor_sentimen": 1,
                        "matriks_strategi": "Gagal Analisis AI",
                        "konfirmasi_tren_mingguan": "Unknown",
                        "rekomendasi_buy": "N/A",
                        "take_profit": 0,
                        "stop_loss": 0,
                        "risk_reward_ratio": "N/A",
                        "alasan_analisis": f"Error Exception: {str(e)}"
                    }
                }
                results.append(combined)

        # Jeda aman rate limit jika masih ada chunk berikutnya
        if idx < len(chunks) - 1:
            time.sleep(4)

    # 3. Gabungkan hasil cache dengan hasil analisa baru
    final_results = cached_results + results

    # Sortir berdasarkan ticker agar respons selalu konsisten urutannya
    final_results = sorted(final_results, key=lambda x: x["ticker"])

    return final_results

@router.get("/index/{index_name}")
def screen_index(index_name: str = Path(..., description="Nama indeks: lq45, kompas100, swing_gems")):
    index_name = re.sub(r'[^a-zA-Z0-9_]', '', index_name).lower().strip()

    # 1. Ambil list ticker berdasarkan indeks
    tickers = get_tickers_by_index(index_name)
    if not tickers:
        raise HTTPException(status_code=400, detail=f"Indeks '{index_name}' tidak valid.")

    progress_manager.reset()
    progress_manager.emit("pre_filter", f"Memulai pre-filter untuk {len(tickers)} ticker indeks {index_name.upper()}...", 5, f"{len(tickers)} tickers")

    # 2. Smart Pre-Filtering
    finalists = smart_pre_filter(tickers)
    progress_manager.emit("pre_filter_done", f"Pre-filter selesai: {len(finalists)} lolos dari {len(tickers)} ticker", 30, f"{len(finalists)} finalists")

    # 3. Lempar Finalis ke Gemini AI secara batch
    results = process_batch_ai(finalists)

    progress_manager.emit("done", f"Selesai! {len(results)} saham berhasil dianalisis.", 100, "")
    return {"status": "success", "total_analisis": len(results), "data": results}


@router.post("/screen")
def screen_batch_stocks(payload: BatchScreenRequest):
    progress_manager.reset()
    progress_manager.emit("pre_filter", f"Memulai pre-filter untuk {len(payload.tickers)} ticker...", 5, f"{len(payload.tickers)} tickers")

    # Gunakan Smart Pre-Filtering untuk list custom
    finalists = smart_pre_filter(payload.tickers)
    progress_manager.emit("pre_filter_done", f"Pre-filter selesai: {len(finalists)} lolos dari {len(payload.tickers)} ticker", 30, f"{len(finalists)} finalists")

    # Lempar ke AI Batch Processor
    results = process_batch_ai(finalists)

    progress_manager.emit("done", f"Selesai! {len(results)} saham berhasil dianalisis.", 100, "")
    return {"status": "success", "total_analisis": len(results), "data": results}

@router.get("/{ticker}")
def get_single_stock(ticker: str, ai: bool = True):
    ticker = re.sub(r'[^a-zA-Z0-9]', '', ticker).upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker tidak valid")
        
    # 1. Ambil data mentah dari SQLite / Google Hub
    result = analyze_stock(ticker)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    
    if not ai:
        return {"status": "success", "data": result}
        
    # 2. Teruskan ke AI untuk analisis Pakem V2.0 (Dibungkus dalam array)
    ai_batch = get_ai_analysis_batch([result])
    ai_analysis = ai_batch.get("results", [{}])[0]
    
    # 3. Gabungkan output
    combined_data = {
        **result,
        "ai_analysis": ai_analysis
    }
    
    return {"status": "success", "data": combined_data}


