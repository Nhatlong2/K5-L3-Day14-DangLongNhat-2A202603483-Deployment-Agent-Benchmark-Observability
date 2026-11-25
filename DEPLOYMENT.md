# Deployment Information

## Public URL

https://www.google.com/url?sa=E&source=gmail&q=https://k5-l3-day14-danglongnhat-2a202603483.onrender.com

## Platform

Render (Web Service — Docker, Free tier + Render Key Value / Redis)

## Test Commands (CP6 Verification)

Đặt biến môi trường trước khi chạy (không ghi key vào code hay repo):

```
export BASE="https://k5-l3-day14-danglongnhat-2a202603483.onrender.com"
export AGENT_API_KEY="<your-api-key>"

```

```
# 1. Health check (kết quả: 200)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"

# 2. Readiness check với Redis trên Render (kết quả: 200)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

# 3. Gọi /ask không có API key (kết quả: 401)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'

# 4. Gọi /ask có X-API-Key hợp lệ (kết quả: 200)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'

```

## Environment Variables Set (đặt trên Render Dashboard, không ghi trong code)

* `PORT` (Render tự cấp, mặc định `10000`)

* `ENVIRONMENT=production`

* `REDIS_URL` (Internal Key Value URL của Render Redis)

* `AGENT_API_KEY` (secret đặt trên Render Dashboard)

* `RATE_LIMIT_PER_MINUTE=10`

* `DAILY_BUDGET_USD=1.0`

## Screenshots

* [Deployment dashboard](https://www.google.com/search?q=screenshots/dashboard.png)

* [Service running](https://www.google.com/search?q=screenshots/running.png)

* [Test results](https://www.google.com/search?q=screenshots/test.png)