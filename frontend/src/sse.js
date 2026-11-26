export class RunRealtimeClient {
  constructor({ sseUrl, pollUrl, pollHeaders = {}, onSnapshot, onReaction }) {
    this.sseUrl = sseUrl;
    this.pollUrl = pollUrl;
    this.pollHeaders = pollHeaders;
    this.onSnapshot = onSnapshot;
    this.onReaction = onReaction;
    this.eventSource = null;
    this.pollTimer = null;
    this.clockOffsetMs = 0;
    this.closed = false;
  }

  start() {
    this.closed = false;
    this._connectSse();
  }

  stop() {
    this.closed = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  nowServerMs() {
    return Date.now() + this.clockOffsetMs;
  }

  _updateOffset(serverTimeIso, rttMs = 0) {
    if (!serverTimeIso) {
      return;
    }
    const serverMs = Date.parse(serverTimeIso);
    if (!Number.isNaN(serverMs)) {
      this.clockOffsetMs = serverMs + rttMs / 2 - Date.now();
    }
  }

  _connectSse() {
    if (this.closed) {
      return;
    }
    try {
      const es = new EventSource(this.sseUrl);
      this.eventSource = es;

      es.addEventListener("snapshot", (ev) => {
        const data = JSON.parse(ev.data);
        this._updateOffset(data.server_time, 0);
        if (this.onSnapshot) {
          this.onSnapshot(data);
        }
      });

      es.addEventListener("reaction", (ev) => {
        const data = JSON.parse(ev.data);
        if (this.onReaction) {
          this.onReaction(data);
        }
      });

      es.onerror = () => {
        if (!this.pollTimer && !this.closed) {
          this._startFallbackPolling();
        }
      };
    } catch {
      this._startFallbackPolling();
    }
  }

  _startFallbackPolling() {
    if (this.pollTimer || this.closed) {
      return;
    }
    const pollOnce = async () => {
      const t0 = performance.now();
      try {
        const res = await fetch(this.pollUrl, {
          credentials: "same-origin",
          headers: this.pollHeaders,
        });
        if (!res.ok) {
          return;
        }
        const rtt = performance.now() - t0;
        const data = await res.json();
        this._updateOffset(data.server_time, rtt);
        if (this.onSnapshot) {
          this.onSnapshot(data);
        }
      } catch {
      }
    };
    pollOnce();
    this.pollTimer = setInterval(pollOnce, 1500);
  }
}
