function fetchProfile() {
    if(activeUser) {
        document.getElementById('profileUsername').textContent = activeUser.username;
        document.getElementById('profileEmail').textContent = activeUser.email;
    }
    if(activePortfolio) {
        document.getElementById('profileActivePortfolio').textContent = activePortfolio.name;
        document.getElementById('profileInitialBalance').textContent = `Initial Balance: Rp ${activePortfolio.initial_balance.toLocaleString('id-ID')}`;
        document.getElementById('inputRiskPct').value = activePortfolio.risk_per_trade_pct || 10;
    }
}

async function saveTradingPreferences() {
    if(!activePortfolio) return;
    const riskPct = parseFloat(document.getElementById('inputRiskPct').value);
    if(isNaN(riskPct) || riskPct <= 0 || riskPct > 100) return alert("Masukkan persentase yang valid (0-100)");
    
    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/settings`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ risk_per_trade_pct: riskPct })
        });
        
        if(res.ok) {
            const data = await res.json();
            
            // update local activePortfolio
            const index = portfolios.findIndex(p => p.id === activePortfolio.id);
            if(index !== -1) {
                portfolios[index] = data.portfolio;
            }
            activePortfolio = data.portfolio;
            
            const toast = document.getElementById('toast-preferences');
            toast.classList.remove('hidden');
            setTimeout(() => toast.classList.add('hidden'), 3000);
        } else {
            const data = await res.json();
            alert("Gagal menyimpan preferences: " + (data.detail || ''));
        }
    } catch (e) {
        alert("Error: " + e.message);
    }
}
