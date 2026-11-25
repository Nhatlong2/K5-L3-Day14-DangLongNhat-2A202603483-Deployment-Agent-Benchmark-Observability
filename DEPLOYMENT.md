# Deployment Information

## Public URL
https://[THAY-BANG-URL-PUBLIC-CUA-BAN]

## Platform
[Railway hoặc Render]

## Test Commands (CP6 Verification)

Đặt biến môi trường trước khi chạy:
```bash
export BASE="https://[THAY-BANG-URL-PUBLIC-CUA-BAN]"
export AGENT_API_KEY="<your-api-key>"
```

```bash
# 1. Health check (mong đợi: 200)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"

# 2. Readiness check với Redis trên cloud (mong đợi: 200)
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

# 3. Gọi /ask không có API key (mong đợi: 401)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'

# 4. Gọi /ask có X-API-Key hợp lệ (mong đợi: 200)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

## Environment Variables Set (trên Dashboard, không ghi trong code)
- `PORT` (nền tảng tự cấp hoặc `8000`)
- `ENVIRONMENT=production`
- `REDIS_URL` (trỏ tới Redis service trên cloud)
- `AGENT_API_KEY` (secret đặt trên Dashboard)
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
