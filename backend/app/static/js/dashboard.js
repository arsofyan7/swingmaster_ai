let eqChartInst = null;
let scChartInst = null;

async function fetchDashboard(silent = false) {
    if(!activePortfolio) return;
    if(!silent) {
        document.getElementById('dashboard-skeleton').classList.remove('hidden');
        document.getElementById('dashboard-content').classList.add('hidden');
    }
    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/dashboard`);
        const data = await res.json();
        if(data.status === 'success') {
            localStorage.setItem("last_dashboard_snapshot", JSON.stringify(data));
            renderDashboardCards(data);
            renderDashboardAlerts(data.alerts);
            renderDashboardPositions(data.active_positions);
            renderCharts(data.equity_curve, data.sector_allocation);

            // Initialize IHSG Lightweight Chart
            const ihsgContainer = document.getElementById('ihsg_chart_container');
            if (ihsgContainer) {
                ihsgContainer.innerHTML = '';
                const isDark = document.documentElement.classList.contains('dark');
                const chartOptions = { 
                  layout: { 
                    background: { type: 'solid', color: isDark ? '#111827' : '#ffffff' }, 
                    textColor: isDark ? '#9CA3AF' : '#4B5563' 
                  }, 
                  grid: { 
                    vertLines: { color: isDark ? '#1F2937' : '#E5E7EB', style: 1 }, 
                    horzLines: { color: isDark ? '#1F2937' : '#E5E7EB', style: 1 } 
                  },
                  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                  rightPriceScale: { borderColor: isDark ? '#374151' : '#E5E7EB' },
                  timeScale: { borderColor: isDark ? '#374151' : '#E5E7EB', timeVisible: true },
                  watermark: { 
                    color: isDark ? 'rgba(55, 65, 81, 0.4)' : 'rgba(229, 231, 235, 0.6)', 
                    visible: true, 
                    text: 'IHSG', 
                    fontSize: 48, 
                    horzAlign: 'center', 
                    vertAlign: 'center' 
                  },
                  width: ihsgContainer.clientWidth || 800,
                  height: 300 
                };
                const chart = LightweightCharts.createChart(ihsgContainer, chartOptions);
                const areaSeries = chart.addSeries(LightweightCharts.AreaSeries, { 
                    lineColor: '#3b82f6', 
                    topColor: 'rgba(59, 130, 246, 0.4)', 
                    bottomColor: 'rgba(59, 130, 246, 0.0)',
                    lineWidth: 2
                });
                
                const sortedData = (data.ihsg_history || []).sort((a, b) => a.time.localeCompare(b.time));
                areaSeries.setData(sortedData);
                chart.timeScale().fitContent();

                // Handle resize
                if (window.ihsgResizeObserver) {
                    window.ihsgResizeObserver.disconnect();
                }
                window.ihsgResizeObserver = new ResizeObserver(entries => {
                    if (entries.length === 0) return;
                    const newWidth = entries[0].contentRect.width;
                    chart.resize(newWidth, 300);
                });
                window.ihsgResizeObserver.observe(ihsgContainer);
            }
        }
    } catch(e) {
        console.error("Failed to load dashboard", e);
    } finally {
        document.getElementById('dashboard-skeleton').classList.add('hidden');
        document.getElementById('dashboard-content').classList.remove('hidden');
    }
}

function renderDashboardCards(data) {
    document.getElementById('dash-equity').textContent = `Rp ${data.balance_info.total_equity.toLocaleString('id-ID')}`;
    document.getElementById('dash-cash').textContent = `Rp ${data.balance_info.current_balance.toLocaleString('id-ID')}`;
    document.getElementById('dash-invested').textContent = `Rp ${data.balance_info.total_invested.toLocaleString('id-ID')}`;
    document.getElementById('dash-winrate').textContent = `${data.metrics.win_rate}%`;
    document.getElementById('dash-mdd').textContent = `-${data.metrics.mdd}%`;
}

function renderDashboardAlerts(alerts) {
    const container = document.getElementById('dashboard-alerts');
    container.innerHTML = '';
    alerts.forEach(msg => {
        const div = document.createElement('div');
        div.className = "p-3 rounded-md bg-yellow-50 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800 text-sm flex items-center";
        div.innerHTML = `<span class="mr-2 text-lg">⚠️</span> ${msg}`;
        container.appendChild(div);
    });
}

function renderDashboardPositions(positions) {
    const tbody = document.getElementById('activePositionsTable');
    tbody.innerHTML = '';
    if(!positions || positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-gray-500">No active positions found.</td></tr>';
        return;
    }

    positions.forEach(p => {
        const tr = document.createElement('tr');
        
        let rowColorClass = "hover:bg-gray-50 dark:hover:bg-gray-800/50";
        let actionBtn = `<button onclick="openClosePositionModal('${p.ticker}', ${p.current_price})" class="text-xs bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 px-3 py-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition">Close</button>`;

        if(p.current_price >= p.target_tp) {
            rowColorClass = "bg-green-50 dark:bg-green-900/20";
            actionBtn = `<button onclick="openClosePositionModal('${p.ticker}', ${p.current_price})" class="text-xs bg-green-500 text-white px-3 py-1 rounded animate-pulse shadow-sm">Take Profit!</button>`;
        } else if(p.current_price <= p.target_sl) {
            rowColorClass = "bg-red-50 dark:bg-red-900/20";
            actionBtn = `<button onclick="openClosePositionModal('${p.ticker}', ${p.current_price})" class="text-xs bg-red-500 text-white px-3 py-1 rounded animate-pulse shadow-sm">Stop Loss!</button>`;
        }

        tr.className = `transition ${rowColorClass}`;
        
        const pnlColor = p.floating_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
        const pnlSign = p.floating_pnl >= 0 ? '+' : '';

        const investedRp = p.buy_price * p.total_lot * 100;
        const pnlPct = investedRp > 0 ? (p.floating_pnl / investedRp) * 100 : 0;

        tr.innerHTML = `
            <td class="p-3 font-bold text-blue-600 dark:text-blue-400">${p.ticker}</td>
            <td class="p-3">${p.buy_price.toLocaleString('id-ID')}</td>
            <td class="p-3 font-semibold">${p.current_price.toLocaleString('id-ID')}</td>
            <td class="p-3 text-green-600 dark:text-green-400">${p.target_tp ? p.target_tp.toLocaleString('id-ID') : '-'}</td>
            <td class="p-3 text-red-600 dark:text-red-400">${p.target_sl ? p.target_sl.toLocaleString('id-ID') : '-'}</td>
            <td class="p-3">${p.total_lot.toLocaleString('id-ID')}</td>
            <td class="p-3">${investedRp.toLocaleString('id-ID')}</td>
            <td class="p-3 font-bold ${pnlColor}">${pnlSign}${p.floating_pnl.toLocaleString('id-ID')}</td>
            <td class="p-3 font-semibold ${pnlColor}">${pnlSign}${pnlPct.toFixed(2)}%</td>
            <td class="p-3 text-center">${actionBtn}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderCharts(equityData, sectorData) {
    const isDark = document.documentElement.classList.contains('dark');
    const gridColor = isDark ? '#334155' : '#e2e8f0';
    const textColor = isDark ? '#94a3b8' : '#64748b';

    // Equity Curve
    const eqCanvas = document.getElementById('equityChart');
    if(eqChartInst) eqChartInst.destroy();
    
    const labels = equityData.map(d => d.date);
    const dataPts = equityData.map(d => d.total_equity);
    
    eqChartInst = new Chart(eqCanvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Equity (Rp)',
                data: dataPts,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { grid: { color: gridColor }, ticks: { color: textColor } },
                y: { grid: { color: gridColor }, ticks: { color: textColor } }
            },
            plugins: { legend: { display: false } }
        }
    });

    // Sector Doughnut
    const scCanvas = document.getElementById('sectorChart');
    if(scChartInst) scChartInst.destroy();
    
    const secLabels = Object.keys(sectorData);
    const secData = Object.values(sectorData);
    
    if(secLabels.length === 0) {
        secLabels.push("No Active Positions");
        secData.push(1);
    }

    scChartInst = new Chart(scCanvas, {
        type: 'doughnut',
        data: {
            labels: secLabels,
            datasets: [{
                data: secData,
                backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#64748b'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { color: textColor, boxWidth: 12 } }
            }
        }
    });
}
