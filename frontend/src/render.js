let katexModule = null;
let purifyModule = null;
let markedModule = null;
let mermaidModule = null;

async function ensureRenderers() {
  if (!purifyModule) {
    const [purify, marked] = await Promise.all([import("dompurify"), import("marked")]);
    purifyModule = purify.default || purify;
    markedModule = marked;
  }
}

async function ensureKatex() {
  if (!katexModule) {
    const mod = await import("katex");
    katexModule = mod.default || mod;
  }
}

async function ensureMermaid() {
  if (!mermaidModule) {
    const mod = await import("mermaid");
    mermaidModule = mod.default || mod;
    mermaidModule.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark" });
  }
}

export async function renderRichContent(container, text, sandboxHtml = "") {
  await ensureRenderers();
  const raw = String(text || "");
  const hasMath = raw.includes("$");
  let processed = raw;

  if (hasMath) {
    await ensureKatex();
    processed = processed.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
      try {
        return katexModule.renderToString(expr.trim(), { displayMode: true, trust: false, throwOnError: false });
      } catch {
        return expr;
      }
    });
    processed = processed.replace(/\$([^\n$]+?)\$/g, (_, expr) => {
      try {
        return katexModule.renderToString(expr.trim(), { displayMode: false, trust: false, throwOnError: false });
      } catch {
        return expr;
      }
    });
  }

  const html = markedModule.parse(processed);
  container.innerHTML = purifyModule.sanitize(html, {
    ADD_TAGS: ["math", "semantics", "mrow", "mi", "mo", "mn", "msup", "msub", "mfrac", "annotation"],
    ADD_ATTR: ["aria-hidden", "style", "class"],
  });

  const mermaidBlocks = container.querySelectorAll("code.language-mermaid");
  if (mermaidBlocks.length > 0) {
    await ensureMermaid();
    for (const block of mermaidBlocks) {
      const pre = block.parentElement;
      const wrapper = document.createElement("div");
      wrapper.className = "mermaid";
      wrapper.textContent = block.textContent || "";
      pre.replaceWith(wrapper);
    }
    await mermaidModule.run({ nodes: container.querySelectorAll(".mermaid") });
  }

  if (sandboxHtml) {
    const iframe = document.createElement("iframe");
    iframe.className = "sandbox-frame";
    iframe.setAttribute("sandbox", "allow-scripts");
    iframe.setAttribute(
      "srcdoc",
      `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';"></head><body>${sandboxHtml}</body></html>`
    );
    container.appendChild(iframe);
  }
}

export function applyCopyProtection(enabled) {
  document.body.classList.toggle("no-copy", Boolean(enabled));
  const block = (ev) => {
    if (enabled) {
      ev.preventDefault();
    }
  };
  document.oncontextmenu = enabled ? block : null;
  document.oncopy = enabled ? block : null;
}
