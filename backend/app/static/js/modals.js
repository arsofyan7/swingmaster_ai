let selectedStockData = null;
let closePositionTicker = null;

function openActionMenu(item) {
    selectedStockData = item;
    document.getElementById('actionModalTitle').textContent = `${item.ticker} - Action`;
    document.getElementById('actionModal').classList.remove('hidden');
}

function closeActionModal() {
    document.getElementById('actionModal').classList.add('hidden');
    selectedStockData = null;
}

function openTradingViewChart() {
    if(!selectedStockData) return;
    const ticker = selectedStockData.ticker;
    window.open(`https://id.tradingview.com/chart/?symbol=IDX:${ticker}`, '_blank');
    closeActionModal();
}

function openChartModal() {
    if(!selectedStockData) return;
    document.getElementById('actionModal').classList.add('hidden');
    const modal = document.getElementById('chartModal');
    modal.classList.remove('hidden');
    
    const container = document.getElementById('tv_chart_container');
    container.innerHTML = '';
    
    const ticker = selectedStockData.ticker;
    const chartOptions = { 
      layout: { 
        background: { type: 'solid', color: '#111827' }, 
        textColor: '#9CA3AF' 
      }, 
      grid: { 
        vertLines: { color: '#1F2937', style: 1 }, 
        horzLines: { color: '#1F2937', style: 1 } 
      },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#374151' },
      timeScale: { borderColor: '#374151', timeVisible: true },
      watermark: { 
        color: 'rgba(55, 65, 81, 0.4)', 
        visible: true, 
        text: ticker, 
        fontSize: 48, 
        horzAlign: 'center', 
        vertAlign: 'center' 
      },
      width: container.clientWidth || 800,
      height: 400 
    };
    
    const chart = LightweightCharts.createChart(container, chartOptions);
    const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, { 
        upColor: '#22c55e', 
        downColor: '#ef4444', 
        borderVisible: false, 
        wickUpColor: '#22c55e', 
        wickDownColor: '#ef4444' 
    });

    const volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '', // Set to empty string for a separate overlay scale
        scaleMargins: { top: 0.8, bottom: 0 } // volume on bottom 20%
    });

    // Format data from history_ohlcv
    const sortedHistory = (selectedStockData.history_ohlcv || []).slice().sort((a, b) => {
        const tA = a.date || a.time;
        const tB = b.date || b.time;
        return tA.localeCompare(tB);
    });

    const formattedOhlcvData = sortedHistory.map(h => ({
        time: h.date || h.time,
        open: parseFloat(h.open),
        high: parseFloat(h.high),
        low: parseFloat(h.low),
        close: parseFloat(h.close)
    }));

    const volumeData = sortedHistory.map(h => ({
        time: h.date || h.time,
        value: parseFloat(h.volume || 0),
        color: parseFloat(h.close) > parseFloat(h.open) ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)'
    }));

    if (formattedOhlcvData.length > 0) {
        candleSeries.setData(formattedOhlcvData);
        volumeSeries.setData(volumeData);
        chart.timeScale().fitContent();
    } else {
        container.innerHTML = '<div class="h-full flex items-center justify-center text-gray-500">Tidak ada data historis OHLCV.</div>';
        return;
    }

    // Handle resize
    const resizeObserver = new ResizeObserver(entries => {
        if (entries.length === 0) return;
        const newWidth = entries[0].contentRect.width;
        chart.resize(newWidth, 400);
    });
    resizeObserver.observe(container);
    
    // Store instance on the container to destroy if needed on close
    container.chartInstance = chart;
    container.resizeObserverInstance = resizeObserver;
}

function closeChartModal() {
    document.getElementById('chartModal').classList.add('hidden');
    const container = document.getElementById('tv_chart_container');
    if (container.resizeObserverInstance) {
        container.resizeObserverInstance.disconnect();
        delete container.resizeObserverInstance;
    }
    container.innerHTML = '';
    if (container.chartInstance) {
        delete container.chartInstance;
    }
}

function openBuyModal() {
    if(!selectedStockData || !activePortfolio) return;
    document.getElementById('actionModal').classList.add('hidden');
    
    document.getElementById('buyModalSubtitle').textContent = `${selectedStockData.ticker} - ${selectedStockData.company_name || 'Stock'}`;
    
    const ai = selectedStockData.ai_analysis || {};
    const currentPrice = selectedStockData.filters?.price?.value || 0;
    
    let buyPrice = currentPrice;
    if(ai.rekomendasi_buy) {
        const numbers = String(ai.rekomendasi_buy).match(/\d+/g);
        if(numbers && numbers.length > 0) {
            buyPrice = Math.max(...numbers.map(Number));
        }
    }
    
    let tp = ai.take_profit || 0;
    let sl = ai.stop_loss || 0;
    
    const riskPct = activePortfolio.risk_per_trade_pct || 10;
    const balance = activePortfolio.initial_balance || 100000000;
    const budget = balance * (riskPct / 100);
    let lot = Math.floor(budget / (buyPrice * 100));
    if(lot < 1) lot = 1;

    document.getElementById('inputBuyPrice').value = buyPrice;
    document.getElementById('inputLot').value = lot;
    document.getElementById('inputTP').value = tp;
    document.getElementById('inputSL').value = sl;
    
    calcBuyModal();
    document.getElementById('buyModal').classList.remove('hidden');
}

function closeBuyModal() {
    document.getElementById('buyModal').classList.add('hidden');
}

function calcBuyModal() {
    const bp = parseFloat(document.getElementById('inputBuyPrice').value) || 0;
    const lot = parseInt(document.getElementById('inputLot').value) || 0;
    const tp = parseFloat(document.getElementById('inputTP').value) || 0;
    const sl = parseFloat(document.getElementById('inputSL').value) || 0;

    const totalInvest = bp * lot * 100;
    const cuan = (tp - bp) * lot * 100;
    const rugi = (bp - sl) * lot * 100;

    document.getElementById('buyTotalInvest').textContent = `Rp ${totalInvest.toLocaleString('id-ID')}`;
    
    const cuanEl = document.getElementById('buyPotensiCuan');
    cuanEl.textContent = `+Rp ${cuan > 0 ? cuan.toLocaleString('id-ID') : 0}`;
    
    const rugiEl = document.getElementById('buyRisikoRugi');
    rugiEl.textContent = `-Rp ${rugi > 0 ? rugi.toLocaleString('id-ID') : 0}`;
}

async function executePaperTrade() {
    if(!selectedStockData || !activePortfolio) return;
    
    const bp = parseFloat(document.getElementById('inputBuyPrice').value) || 0;
    const lot = parseInt(document.getElementById('inputLot').value) || 0;
    const tp = parseFloat(document.getElementById('inputTP').value) || 0;
    const sl = parseFloat(document.getElementById('inputSL').value) || 0;

    if(bp <= 0 || lot <= 0) return alert("Harga Beli dan Lot harus lebih dari 0!");

    const payload = {
        ticker: selectedStockData.ticker,
        buy_price: bp,
        total_lot: lot,
        target_tp: tp,
        target_sl: sl
    };

    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/buy`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if(res.ok) {
            alert("✅ PAPER TRADE EXECUTED!\n" + data.message + "\nSisa Saldo: Rp " + data.remaining_balance.toLocaleString('id-ID') + "\n\nSilakan cek Command Center untuk melihat posisi ini.");
            closeBuyModal();
            await loadPortfolios();
            if(!document.getElementById('view-dashboard').classList.contains('hidden')) {
                fetchDashboard();
            }
        } else {
            alert("❌ GAGAL: " + data.detail);
        }
    } catch(e) {
        alert("Error: " + e.message);
    }
}

function openClosePositionModal(ticker, currentPrice) {
    closePositionTicker = ticker;
    document.getElementById('closeModalSubtitle').textContent = ticker;
    document.getElementById('inputSellPrice').value = currentPrice;
    document.getElementById('selectPsychologicalTag').value = "Disiplin Sesuai Plan";
    document.getElementById('inputCloseNotes').value = "";
    document.getElementById('closePositionModal').classList.remove('hidden');
}

function closeClosePositionModal() {
    document.getElementById('closePositionModal').classList.add('hidden');
    closePositionTicker = null;
}

async function executeClosePosition() {
    if(!closePositionTicker || !activePortfolio) return;
    const sellPrice = parseFloat(document.getElementById('inputSellPrice').value) || 0;
    const tag = document.getElementById('selectPsychologicalTag').value;
    const notes = document.getElementById('inputCloseNotes').value;

    if(sellPrice <= 0) return alert("Harga jual harus lebih besar dari 0!");

    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/positions/${closePositionTicker}/close`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                sell_price: sellPrice,
                tag: tag,
                notes: notes
            })
        });
        const data = await res.json();
        if(res.ok) {
            alert("✅ POSISI BERHASIL DITUTUP!");
            closeClosePositionModal();
            await loadPortfolios();
            fetchDashboard();
        } else {
            alert("❌ GAGAL: " + data.detail);
        }
    } catch(e) {
        alert("Error: " + e.message);
    }
}
