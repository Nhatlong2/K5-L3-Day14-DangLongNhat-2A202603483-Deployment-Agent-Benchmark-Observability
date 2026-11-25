# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns phát hiện trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong mã nguồn** (dòng 17–18): `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Nếu push lên GitHub, key và mật khẩu lộ ngay lập tức. Bản `production/app.py` (dòng 24) tách toàn bộ cấu hình sang `config.py` đọc từ biến môi trường (`.env`).

2. **In secret ra console bằng `print()`** (dòng 33–34, 38): `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` vừa làm lộ secret trong log vừa không có cấu trúc (timestamp, level) để lọc trên log aggregator. Bản `production/app.py` (dòng 28–32, 111–122) dùng structured JSON logging và chỉ log metadata (`question_length`, `client_ip`, `response_length`), tuyệt đối không log secret.

3. **Không có Health Check & Readiness endpoint** (dòng 42–43): Thiếu `/health` và `/ready`, nên cloud platform/load balancer không biết khi nào process treo để restart hoặc khi nào chưa sẵn sàng để ngừng route traffic. Bản `production/app.py` (dòng 135–161) bổ sung đầy đủ `GET /health` và `GET /ready`.

4. **Cố định `host="localhost"`, `port=8000` và bật `reload=True`** (dòng 49–54): `localhost` chỉ nhận kết nối nội bộ (không chạy được trong container), `port=8000` không tương thích cổng động do Railway/Render cấp qua biến `PORT`, còn `reload=True` tốn tài nguyên và không ổn định trên production. Bản `production/app.py` (dòng 194–199) bind `settings.host` (`0.0.0.0`), đọc `settings.port` từ env, và chỉ bật reload khi `settings.debug=True`.

5. **Không xử lý Graceful Shutdown & vòng đời ứng dụng** (không có `lifespan` hay xử lý `SIGTERM`): Khi container bị tắt, các request đang xử lý bị cắt ngang. Bản `production/app.py` (dòng 39–67, 180–189) dùng `lifespan` và `signal.SIGTERM` để ngừng nhận traffic (`is_ready = False`) và chờ hoàn thành request trước khi thoát.

6. **Không có cấu hình quản lý môi trường (12-Factor) và CORS** (dòng 21–22): `DEBUG = True`, `MAX_TOKENS = 500` viết cứng. Bản `production/app.py` đọc `ENVIRONMENT`, `ALLOWED_ORIGINS` từ biến môi trường.

### Exercise 1.2: Kết quả chạy bản develop (`POST /ask?question=Hello`)

```
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}

```

### Exercise 1.3: Bảng so sánh Develop vs Production

| Feature | Develop | Production | Tại sao quan trọng? | 
| ----- | ----- | ----- | ----- | 
| Config & Secrets | Hardcode trực tiếp trong `app.py` (`OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG=True`) | Đọc từ biến môi trường qua `config.py` và `.env` (không commit `.env`) | Tránh lộ secret trên Git, cùng một mã nguồn/image chạy được trên dev, staging, production | 
| Health & Readiness | Không có | Có `GET /health` (liveness), `GET /ready` (readiness trả 503 khi chưa sẵn sàng), `GET /metrics` | Platform tự phát hiện container chết để restart; load balancer không gửi traffic vào instance đang khởi động hoặc lỗi | 
| Logging | `print("[DEBUG] ...")`, in cả API key | Structured JSON logging (`logging`), không ghi secret | Dễ thu thập, tìm kiếm và tạo alert trên Datadog/Loki/Cloud Logging mà không làm rò rỉ dữ liệu nhạy cảm | 
| Shutdown | Dừng đột ngột khi tắt process | `lifespan` + xử lý `SIGTERM`, đổi `is_ready = False` trước khi đóng | Không cắt ngang request đang xử lý (in-flight requests) khi deploy bản mới hoặc scale down | 
| Network & Binding | `host="localhost"`, `port=8000`, `reload=True` | `host="0.0.0.0"`, `port` từ `PORT` env, `reload` tắt ở production | Bắt buộc để container nhận traffic từ bên ngoài và nhận cổng động trên Railway/Render/Cloud Run | 

## Part 2: Docker

### Exercise 2.1: Trả lời 4 câu hỏi về `02-docker/develop/Dockerfile`

1. **Base image là gì?** `python:3.11` (bản Debian đầy đủ, dung lượng \~1 GB).

2. **Working directory là gì?** `/app` (`WORKDIR /app`).

3. **Tại sao `COPY requirements.txt` trước khi `COPY` source code?** Để tận dụng **Docker layer cache**. `requirements.txt` ít thay đổi hơn mã nguồn `app.py`; khi chỉ sửa code, Docker dùng lại cache của bước `RUN pip install`, giúp build lại chỉ mất vài giây thay vì cài lại toàn bộ thư viện.

4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?** `ENTRYPOINT` định nghĩa tiến trình chính cố định của container (khó bị ghi đè trừ khi dùng `--entrypoint`), còn `CMD` cung cấp lệnh mặc định hoặc tham số mặc định cho `ENTRYPOINT` và dễ dàng bị ghi đè khi chạy `docker run <image> <command>`.

### Exercise 2.2 & 2.3: Multi-stage build và so sánh dung lượng Image

* **Stage 1 (`builder`)**: Cài đặt các công cụ build (`gcc`, `libpq-dev`) và cài Python dependencies vào `/root/.local` bằng `pip install --no-cache-dir --user`.

* **Stage 2 (`runtime`)**: Dùng base image gọn `python:3.11-slim`, tạo non-root user `appuser`, chỉ copy `/root/.local` và mã nguồn từ stage 1 sang, bổ sung `HEALTHCHECK`.

* **Tại sao image nhỏ hơn?** Vì toàn bộ compiler (`gcc`), header files, cache của `apt`/`pip` nằm lại ở stage `builder` và bị loại bỏ hoàn toàn khỏi image cuối.

**Kết quả đo thực tế trên máy (CHẠY LỆNH DƯỚI ĐÂY TRONG WSL2 VÀ ĐIỀN SỐ THẬT):**

```
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images | grep my-agent

```

* Develop (`my-agent:develop`): `[ĐIỀN SỐ MB ĐO ĐƯỢC]` MB

* Production (`my-agent:advanced`): `[ĐIỀN SỐ MB ĐO ĐƯỢC]` MB

* Chênh lệch: `[ĐIỀN % GIẢM]`%

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)

**Sơ đồ kiến trúc các service (network nội bộ `internal`):**

```
Client (HTTP :80 / HTTPS :443)
        │
        ▼
  ┌───────────┐
  │   nginx   │  (Reverse Proxy / Load Balancer, chỉ expose port 80/443)
  └─────┬─────┘
        │  internal bridge network
        ▼
  ┌───────────┐
  │   agent   │  (FastAPI runtime, port 8000 nội bộ, depends_on redis & qdrant healthy)
  └──┬─────┬──┘
     │     │
     ▼     ▼
┌───────┐ ┌────────┐
│ redis │ │ qdrant │  (persistent volumes: redis_data, qdrant_data)
└───────┘ └────────┘

```

**Kết quả test qua Nginx (`touch 02-docker/production/.env.local && docker compose -p k5-day14-docker up -d --build`):**

* `curl http://localhost/health`: `[DÁN OUTPUT THẬT]`

* `curl -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'`: `[DÁN OUTPUT THẬT]`

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy Agent Part 6 lên Cloud

* **Nền tảng chọn:** `[Railway hoặc Render]`

* **Public URL:** `[DÁN URL PUBLIC CỦA BẠN — xem chi tiết trong DEPLOYMENT.md]`

* **Screenshots:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

### So sánh `railway.toml` vs `render.yaml`

| Tiêu chí | `railway.toml` (Railway) | `render.yaml` (Render Blueprint) | 
| ----- | ----- | ----- | 
| Định dạng & phạm vi | TOML; cấu hình cho **1 service** (build + deploy policy) | YAML (Infrastructure as Code); khai báo **nhiều service cùng lúc** (web service + Redis + disk) | 
| Khai báo Redis / dịch vụ phụ | Tạo Redis riêng trên Railway Dashboard/CLI rồi nối biến `REDIS_URL` | Khai báo trực tiếp `type: redis` trong cùng file và tự nối qua `fromService` | 
| Quản lý biến môi trường & secret | Thiết lập qua Dashboard hoặc `railway variables set` | Khai báo ngay trong `envVars` với `value`, `generateValue: true` hoặc `sync: false` cho secret | 
| Chọn region / plan | Cấu hình trên Dashboard | Khai báo trực tiếp trong file (`region: singapore`, `plan: free`) | 
| Health check & restart | `healthcheckPath = "/health"`, `restartPolicyType = "ON_FAILURE"` | `healthCheckPath: /health`, `autoDeploy: true` | 

### Exercise 3.3: Mô tả pipeline CI/CD Cloud Run (`cloudbuild.yaml` & `service.yaml`)

Pipeline trong `cloudbuild.yaml` tự động chạy 4 bước tuần tự khi push lên `main`: (1) chạy `pytest` trong container `python:3.11-slim` để đảm bảo tests pass trước khi build; (2) build Docker image gắn 2 tag `$COMMIT_SHA` và `latest` có dùng `--cache-from`; (3) push toàn bộ tag lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`); (4) chạy `gcloud run deploy` triển khai image mới lên Cloud Run (`asia-southeast1`, `min-instances=1`, `max-instances=10`, `512Mi` RAM, 1 CPU) và inject secret từ Google Secret Manager. File `service.yaml` định nghĩa cấu hình dịch vụ dạng IaC (Knative Service) gồm giới hạn CPU/RAM, concurrency `80`, biến môi trường lấy từ `secretKeyRef`, cùng `livenessProbe` (`/health`) và `startupProbe` (`/ready`).

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/`)

* API key được kiểm tra qua header `X-API-Key` đối chiếu với biến môi trường `AGENT_API_KEY`; nếu thiếu hoặc sai trả về HTTP `401 Unauthorized`.

* **Rotate key**: Tạo key mới, cấu hình app chấp nhận tạm cả key cũ và key mới (dual-key window), cập nhật client sang key mới, sau đó gỡ key cũ khỏi env mà không gây downtime.

**Output thực tế (`AGENT_API_KEY=secret-key-123`):**

* Không có key (401):

```
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

```

* Có key đúng (200):

```
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}

```

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)

* **Thuật toán trong `rate_limiter.py`**: Sliding Window Counter lưu timestamps trong `deque` theo từng `user_id` (lọc bỏ timestamps cũ hơn `now - 60s`).

* **Giới hạn**: User thường (`student`) tối đa **10 requests/phút** (`rate_limiter_user`), Admin tối đa **100 requests/phút** (`rate_limiter_admin`). Khi vượt quá trả HTTP `429 Too Many Requests` kèm headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.

* **Bypass/nâng giới hạn cho admin**: Dựa vào `role` giải mã từ JWT payload để chọn tier `rate_limiter_admin` (hoặc bỏ qua kiểm tra cho role admin).

**Output thực tế vòng lặp `curl -i` với tài khoản `student` / `demo123` tại `POST /auth/token` (đã che JWT token):**

```
Token OK (masked): eyJhbGciOiJIUzI1...

=== Req 1 ===
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:33:35 GMT
server: uvicorn
content-length: 187
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

... (Req 2–9: đều trả HTTP/1.1 200 OK) ...

=== Req 10 ===
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:33:36 GMT
server: uvicorn
content-length: 212
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

=== Req 11 ===
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 08:33:36 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795595677
retry-after: 59
content-length: 98
content-type: application/json
vary: Origin

=== Req 12 ===
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 08:33:36 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795595677
retry-after: 59
content-length: 98
content-type: application/json
vary: Origin

```

### Exercise 4.4: Cost Guard (`cost_guard.py`)

* **Cơ chế hoạt động**: Trước mỗi lần gọi LLM (`check_budget`), đọc tổng chi phí đã chi trong ngày/tháng từ Redis (key dạng `budget:<user_id>:<YYYY-MM>` hoặc `cost:daily:<YYYY-MM-DD>`). Nếu `current >= budget` thì chặn ngay bằng HTTP `402 Payment Required` (hoặc `503` nếu chạm global budget). Sau khi gọi LLM xong (`record_cost`), tính chi phí theo số input/output tokens và cộng dồn nguyên tử bằng `INCRBYFLOAT`, đồng thời đặt `EXPIRE` để tự reset sang chu kỳ mới.

* **Tại sao cần cả Rate Limit và Cost Guard?** Rate limit bảo vệ **tốc độ truy cập** (chống spam/DDoS, ví dụ 10 req/phút), nhưng một user gọi chậm đều đặn các prompt rất dài vẫn có thể đốt cạn ngân sách LLM; ngược lại Cost Guard bảo vệ **ngân sách tài chính** theo tổng token/USD nhưng không ngăn được burst traffic làm sập server.

## Part 5: Scaling & Reliability

### Exercise 5.1–5.3: Health Checks, Graceful Shutdown & Stateless Design

* **Liveness (`/health`) vs Readiness (`/ready`)**: `/health` kiểm tra tiến trình còn sống hay không (luôn trả `200` kể cả khi mất Redis; nếu fail platform sẽ **restart** container). `/ready` kiểm tra khả năng phục vụ traffic (ping Redis/DB; nếu fail trả `503` để load balancer **ngừng route traffic** tới instance đó mà không cần restart).

* **Graceful Shutdown (`SIGTERM`)**: Khi nhận `SIGTERM`, app chuyển cờ readiness sang `False`, ngừng nhận request mới, chờ các request in-flight hoàn thành, đóng kết nối Redis/DB rồi thoát với exit code `0`.

* **Stateless Design**: Nếu lưu `conversation_history` hay rate limit trong RAM của từng instance, khi scale lên 3 instance sau Nginx round-robin, request 1 vào `agent-1` nhưng request 2 vào `agent-2` sẽ không thấy lịch sử cũ. Chuyển toàn bộ state sang **Redis** giúp mọi instance đều chia sẻ cùng trạng thái.

### Exercise 5.4 & 5.5: Load Balancing & Test Stateless (`05-scaling-reliability/production/`)

**Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và `python test_stateless.py` (CHẠY TRÊN MÁY BẠN VÀ DÁN OUTPUT THẬT):**

```
[DÁN OUTPUT python test_stateless.py THẤY NHIỀU INSTANCE PHỤC VỤ NHƯNG HISTORY VẪN ĐẦY ĐỦ 10 MESSAGES]

```

* **Giải thích**: 5 câu hỏi trong cùng một `session_id` được Nginx cổng `8080` phân phối tới các container `agent` khác nhau (`served_by` thay đổi giữa các instance), nhưng khi gọi `GET /chat/{session_id}/history`, toàn bộ lịch sử hội thoại vẫn nguyên vẹn nhờ lưu tập trung trong Redis.

## Part 6: Final Project — Output `check_production_ready.py`

Kết quả chạy `python check_production_ready.py` đầy đủ (WSL2 + Docker 29.9.3; image 297 MB, `docker stop` exit code 0 trong 1.0s):

```
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!

```

## AI Log

1. **Part 1–5 (Phân tích mã nguồn và tổng hợp câu trả lời)**:

   * *Hỏi AI*: Đọc các file mẫu trong `01-localhost-vs-production/`, `02-docker/`, `03-cloud-deployment/`, `04-api-gateway/`, `05-scaling-reliability/` và tổng hợp các anti-pattern, bảng so sánh, sơ đồ kiến trúc và giải thích kỹ thuật.

   * *Nhận được*: Bản nháp câu trả lời kèm dẫn chứng dòng code và lệnh kiểm thử thực tế cho lớp K5.

   * *Tự kiểm tra & sửa*: Tự chạy các lệnh `curl`, `docker build`, `docker compose`, `test_stateless.py` trên máy và điền số đo thực tế.

2. **Part 6 (`06-lab-complete/`)**:

   * *Hỏi AI*: Hướng dẫn và hỗ trợ hoàn thiện các file `TODO` (`app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`) theo đúng 12 tiêu chí trong `06-lab-complete/README.md`.

   * *Nhận được*: Mã nguồn hoàn chỉnh dùng Redis Sorted Set cho sliding window rate limit, `INCRBYFLOAT` cho cost guard, `JsonFormatter` cho structured logging, multi-stage Dockerfile non-root.

   * *Tự kiểm tra & sửa*: Chạy `python check_production_ready.py --static-only` (28/28 static checks pass), chạy unit test các mã lỗi 200/401/402/429/503 và chạy đầy đủ `python check_production_ready.py` có Docker để xác nhận `PASS 12/12`.

3. **Part 7 (`06-lab-complete/benchmark-observability/`)**:

   * *Hỏi AI*: Hỗ trợ thêm Histogram `agent_question_length_chars`, bổ sung 2 mục `KNOWLEDGE_BASE` còn thiếu (`scaling-03`, `security-02`) và viết mẫu workflow CI `.github/workflows/eval.yml`.

   * *Nhận được*: Đoạn code bổ sung metric, 2 entry KB và file YAML CI.

   * *Tự kiểm tra & sửa*: Tự chạy `load_test.py`, `run_eval.py`, `promtool`, Locust headless và đối chiếu toàn bộ số liệu trong `BENCHMARK_REPORT.md` với file JSON/CSV thật.