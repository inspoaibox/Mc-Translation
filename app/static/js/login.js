// 登录逻辑
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('error-message');

    try {
        const response = await fetch('/admin/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            // 保存 token
            localStorage.setItem('token', data.access_token);
            // 跳转到管理后台
            window.location.href = '/admin/dashboard';
        } else {
            errorDiv.textContent = data.detail || '登录失败，请检查用户名和密码';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = '网络错误，请稍后重试';
        errorDiv.style.display = 'block';
    }
});
