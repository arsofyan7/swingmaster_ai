function checkAuth() {
    const userStr = localStorage.getItem("active_user");
    if(userStr) {
        activeUser = JSON.parse(userStr);
        document.getElementById("auth-screen").classList.add("hidden");
        document.getElementById("main-app").classList.remove("hidden");
        loadPortfolios();
    } else {
        document.getElementById("auth-screen").classList.remove("hidden");
        document.getElementById("main-app").classList.add("hidden");
    }
}

function toggleAuthMode(mode) {
    if(mode === 'register') {
        document.getElementById("login-form").classList.add("hidden");
        document.getElementById("register-form").classList.remove("hidden");
        document.getElementById("auth-subtitle").textContent = "Daftar akun baru";
    } else {
        document.getElementById("login-form").classList.remove("hidden");
        document.getElementById("register-form").classList.add("hidden");
        document.getElementById("auth-subtitle").textContent = "Silakan Login ke akun Anda";
    }
}

async function handleLogin() {
    const u = document.getElementById("login-username").value;
    const p = document.getElementById("login-password").value;
    if(!u || !p) return alert("Isi semua field!");
    
    try {
        const res = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({username: u, password: p})
        });
        const data = await res.json();
        if(!res.ok) throw new Error(data.detail);
        
        localStorage.setItem("active_user", JSON.stringify(data.user));
        checkAuth();
    } catch(e) {
        alert(e.message);
    }
}

async function handleRegister() {
    const u = document.getElementById("register-username").value;
    const e = document.getElementById("register-email").value;
    const p = document.getElementById("register-password").value;
    if(!u || !e || !p) return alert("Isi semua field!");
    
    try {
        const res = await fetch('/api/v1/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({username: u, email: e, password: p})
        });
        const data = await res.json();
        if(!res.ok) throw new Error(data.detail);
        
        localStorage.setItem("active_user", JSON.stringify(data.user));
        checkAuth();
    } catch(err) {
        alert(err.message);
    }
}

function handleLogout() {
    localStorage.removeItem("active_user");
    localStorage.removeItem("active_portfolio");
    activeUser = null;
    activePortfolio = null;
    window.location.reload();
}

// Initialize Auth on script load
checkAuth();
