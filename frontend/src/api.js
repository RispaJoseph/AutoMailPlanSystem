// frontend/src/api.js
const getAuthHeader = () => {
    const token = localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : {};
};

async function request(url, { method = "GET", body = null, headers = {}, expectJson = true } = {}) {
    const opts = {
        method,
        headers: {
            "Content-Type": "application/json",
            ...getAuthHeader(),
            ...headers,
        },
    };
    if (body != null) opts.body = JSON.stringify(body);

    const res = await fetch(url, opts);
    if (!res.ok) {
        const text = await res.text().catch(() => "");
        const err = new Error(`API error ${res.status} ${text}`);
        err.status = res.status;
        err.body = text;
        throw err;
    }
    if (!expectJson) return res;
    return res.json();
}

export { request, getAuthHeader };