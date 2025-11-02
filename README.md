# HTTPS-Server

A high-performance, non-blocking, event-driven HTTPS/WSGI server and static file handler built from scratch in Python using only standard libraries. This project demonstrates core networking concepts, including I/O multiplexing with `selectors`, SSL/TLS, and implementing the PEP 3333 (WSGI) specification.  ## ✨ Features

* **Non-Blocking I/O:** Uses the `selectors` module for efficient, event-driven handling of many concurrent connections in a single process.
* **HTTPS/SSL Enabled:** Securely serves content over HTTPS using the `ssl` module (with self-signed certificates generated on the fly).
* **WSGI Compliant:** Can run any WSGI-compatible Python web application (like Flask, Django, or the included `wsgiapp.py`).
* **Advanced Static File Serving:**
  * **Partial Content (Streaming):** Supports `Range` requests (HTTP 206) for streaming media like the included `.mp4` video.
  * **Caching:** Implements `ETag` and `Last-Modified` headers to handle `304 Not Modified` responses, saving bandwidth.
  * **MIME Types:** Automatically detects and serves the correct `Content-Type`.
* **Load Testing Client:** Includes a multi-process load testing script (`server/client.py`) to stress-test the server's concurrency.

## Project Structure

```bash

.
├── server/
│   ├── webServer.py    \# The core non-blocking server logic
│   └── client.py       \# Multi-process load testing client
├── static/
│   ├── index.html      \# Test HTML page
│   ├── sample.mp4      \# Test video for streaming
│   ├── style.css       \# Test stylesheet
│   ├── script.js       \# Test JavaScript
│   └── hello.txt       \# Test plain text file
├── wsgiapp.py          \# A minimal "Hello World" WSGI application
├── run.sh              \# Main script to run the server
├── test.sh             \# Automated cURL test script
├── cert.pem            \# Auto-generated SSL certificate
└── key.pem             \# Auto-generated SSL private key
```

## Installation

This project uses only the Python standard library. No `pip install` is required.

### 1. Clone the Repository

```bash
git clone https://github.com/carb0ned0/HTTP-Server.git
cd HTTPS-Server
```

### 2. Run the Server

The included `run.sh` script is the easiest way to start. It will automatically generate the required SSL certificates (`cert.pem`, `key.pem`) if they are missing.

```bash
# Make the script executable
chmod +x run.sh

# Run the server
./run.sh
```

You should see the following output, and the server is now running:

```bash
📜 Generating self-signed cert.pem and key.pem...
Starting WSGI HTTPS server at https://localhost:8443/
WSGIServer: Serving HTTP on port 8443 ...

Server is running (non-blocking with selectors)...
```

## How to Test

You can test the server in three ways:

### 1. Web Browser (Manual Test)

1. Open your web browser and navigate to **`https://localhost:8443/static/index.html`**.
2. Your browser will show a security warning ("Your connection is not private"). This is expected because we are using a self-signed certificate. Click **"Advanced"** and then **"Proceed to localhost (unsafe)"**.
3. You should see the `index.html` page, and the `sample.mp4` video should stream correctly.
4. You can test the WSGI application by visiting **`https://localhost:8443/hello`**.

### 2. Automated Test Script (Recommended)

In a **new terminal** (while the server is running), use the `test.sh` script to run a series of automated `curl` tests.

```bash
# Make the script executable
chmod +x test.sh

# Run the tests
./test.sh
```

You should see a successful output as the script tests static files, range requests, and HEAD requests:

```bash
🔍 Testing static file access...

 hello.txt:
This is a plain text file.

 index.html:
<!DOCTYPE html>
<html>
...
</html>

 Range request (sample.mp4 if exists):
$ftypisomisomi

 HEAD request:
HTTP/1.1 200 OK
Content-Type: text/plain
Content-Length: 27
...

✅ Done.
```

### 3. Load Testing

In a **new terminal**, you can use the `client.py` script to simulate a high load. The command below will simulate 5 concurrent clients, each making 100 connections.

```bash
# Syntax: python server/client.py --max-clients <num> --max-conns <num>
python server/client.py --max-clients 5 --max-conns 100
```

You will see output in the client terminal (`Client 0, Connection 0...`) and a flood of requests in your server terminal, demonstrating its ability to handle concurrent connections.

## How It Works

* **`server/webServer.py`**: This is the core of the project. It creates a main `socket`, wraps it with `ssl.SSLContext` for HTTPS, and registers it with a `selectors.DefaultSelector()`.
* **Event Loop**: The server runs in a single-threaded event loop (`serve_forever()`). The `selector.select()` call blocks until a socket is ready for I/O.
    1. If the main server socket is ready, it calls `accept()` to onboard a new client.
    2. If a client socket is ready, it calls `read()` to process the HTTP request.
* **Request Handling**: The `handle_one_request()` method parses the raw HTTP request.
  * If the path starts with `/static/`, it calls `send_static_response()`. This function checks `Range`, `If-Modified-Since`, and `If-None-Match` headers to serve full files, partial content (206), or "not modified" (304) responses.
  * For all other paths, it populates a WSGI `environ` dictionary and calls the `self.application()` (our `wsgiapp.py`) to get the response.

## Roadmap

This project is a functional demonstration, but it could be extended with more features:

* [x] Non-blocking I/O with `selectors`
* [x] HTTPS/SSL support
* [x] WSGI (PEP 3333) compliance
* [x] Static file serving
* [x] Range request support (HTTP 206)
* [x] Caching support (`ETag`, `Last-Modified`, HTTP 304)
* [ ] Implement HTTP/1.1 Keep-Alive connections
* [ ] Add a thread pool for handling blocking WSGI applications
* [ ] More robust HTTP request parsing

## License

Distributed under the MIT License.
