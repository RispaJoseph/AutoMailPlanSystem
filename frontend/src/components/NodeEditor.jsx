// frontend/src/components/NodeEditor.jsx
import React, { useEffect, useState, useRef } from "react";

const TRIGGER_OPTIONS = [
  { value: "on_signup", label: "On Signup" },
  { value: "after_1_day", label: "After 1 Day" },
  { value: "button_click", label: "On Button Click" },
];

/**
 * NodeEditor
 *
 * Props:
 *  - node: the node object { id, type, data }
 *  - onClose: function called when closing panel
 *  - onChange: function(field, value) to update node data in parent
 *
 * Behavior:
 *  - Template Vars area accepts either:
 *      - plain key:value lines (one per line)
 *      - valid JSON object
 *    and it will call onChange("template_vars", parsedObject) when valid.
 *  - When email body contains {{ placeholders }}, editor will prefill missing keys
 *    into the template area so you can just type the values.
 */
export default function NodeEditor({ node, onClose = () => {}, onChange = () => {} }) {
  const [templateRaw, setTemplateRaw] = useState("");
  const [templateError, setTemplateError] = useState(null);
  const [autoFilled, setAutoFilled] = useState(false); // whether we auto filled placeholders
  const prevNodeId = useRef(null);

  // Utility: extract placeholders like {{ first_name }} from body text
  const extractPlaceholders = (text) => {
    if (!text) return [];
    const regex = /{{\s*([a-zA-Z0-9_]+)\s*}}/g;
    const set = new Set();
    let m;
    while ((m = regex.exec(text)) !== null) {
      if (m[1]) set.add(m[1]);
    }
    return Array.from(set);
  };

  // Parse either JSON or "key: value" lines into object
  const parseTemplateVars = (text) => {
    if (!text || text.trim() === "") return {};
    // Try JSON first
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed === "object" && parsed !== null) return parsed;
    } catch (_) {
      // not JSON, try key:value lines
    }
    const lines = text.split("\n");
    const obj = {};
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      // accept "key: value" or "key=value"
      const sepIndex = trimmed.indexOf(":");
      const eqIndex = trimmed.indexOf("=");
      let key, val;
      if (sepIndex > -1) {
        key = trimmed.slice(0, sepIndex).trim();
        val = trimmed.slice(sepIndex + 1).trim();
      } else if (eqIndex > -1) {
        key = trimmed.slice(0, eqIndex).trim();
        val = trimmed.slice(eqIndex + 1).trim();
      } else {
        // if single word, treat as key with empty value
        key = trimmed;
        val = "";
      }
      if (key) obj[key] = val;
    }
    return obj;
  };

  // Pretty-print an object into key: value lines
  const formatTemplateVarsAsLines = (obj) => {
    if (!obj || typeof obj !== "object") return "";
    // preserve insertion order by Object.keys
    return Object.keys(obj)
      .map((k) => `${k}: ${obj[k]}`)
      .join("\n");
  };

  // Initialize templateRaw when node changes
  useEffect(() => {
    if (!node) {
      setTemplateRaw("");
      setTemplateError(null);
      setAutoFilled(false);
      prevNodeId.current = null;
      return;
    }

    const data = node.data || {};
    const tv = data.template_vars || {};

    // If the node changed (different id) or TV was empty, attempt to auto-fill
    const bodyText = (data.body || "").toString();
    const placeholders = extractPlaceholders(bodyText);

    // Create a starting object: merge existing template_vars (tv) and placeholders (placeholders -> "").
    const startingObj = {};

    // Prefer existing tv values
    if (tv && typeof tv === "object") {
      Object.assign(startingObj, tv);
    } else {
      // try parse if string
      try {
        const parsedTv = JSON.parse(tv || "{}");
        if (parsedTv && typeof parsedTv === "object") Object.assign(startingObj, parsedTv);
      } catch (_) {}
    }

    // If placeholders exist, add any missing keys with empty string
    let filled = false;
    placeholders.forEach((ph) => {
      if (!(ph in startingObj)) {
        startingObj[ph] = "";
        filled = true;
      }
    });

    // If template_vars is empty and we have placeholders, show key:value lines (not JSON)
    if ((!tv || (typeof tv === "object" && Object.keys(tv).length === 0)) && placeholders.length > 0) {
      setTemplateRaw(formatTemplateVarsAsLines(startingObj));
      setAutoFilled(true);
      setTemplateError(null);
    } else {
      // If the node id changed, reformat existing tv to lines for convenience
      if (prevNodeId.current !== node.id) {
        setTemplateRaw(formatTemplateVarsAsLines(startingObj));
        setAutoFilled(filled);
        setTemplateError(null);
      } else {
        // keep existing raw (user might be editing)
        try {
          setTemplateRaw(formatTemplateVarsAsLines(startingObj));
        } catch (_) {
          setTemplateRaw("");
        }
      }
    }

    prevNodeId.current = node.id;
    // Also propagate parsed object to parent to ensure node.data.template_vars is set
    try {
      const parsedObj = parseTemplateVars(formatTemplateVarsAsLines(startingObj));
      onChange("template_vars", parsedObj);
    } catch (_) {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node && node.id]); // only when node id changes

  if (!node) {
    return (
      <div className="p-4">
        <div className="text-gray-600">Select a node to edit</div>
      </div>
    );
  }

  const type = node.type;
  const data = node.data || {};

  const change = (field) => (e) => {
    const value = e && e.target ? e.target.value : e;
    onChange(field, value);
  };

  // Called whenever template textarea changes
  const handleTemplateChange = (e) => {
    const text = e.target.value;
    setTemplateRaw(text);
    setTemplateError(null);

    // Blank -> set empty object
    if (!text || text.trim() === "") {
      setTemplateError(null);
      onChange("template_vars", {});
      return;
    }

    try {
      const parsed = parseTemplateVars(text);
      if (parsed && typeof parsed === "object") {
        setTemplateError(null);
        onChange("template_vars", parsed);
      } else {
        setTemplateError("Parsed content must be an object (key:value pairs or JSON).");
      }
    } catch (err) {
      setTemplateError(err.message || "Invalid input");
      // don't call onChange until valid
    }
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-lg font-medium">
          {type === "email" ? "Email Node" : type === "trigger" ? "Trigger Node" : type === "delay" ? "Delay Node" : "Node"}
        </div>
        <button onClick={onClose} className="text-sm text-gray-500">
          Close
        </button>
      </div>

      {type === "trigger" && (
        <div>
          <label className="block text-sm font-medium mb-1">Trigger Type</label>
          <select
            value={data.trigger_type || "button_click"}
            onChange={change("trigger_type")}
            className="w-full p-2 border rounded mb-3"
          >
            {TRIGGER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <label className="block text-sm font-medium mb-1">Label (optional)</label>
          <input
            value={data.label || ""}
            onChange={change("label")}
            className="w-full p-2 border rounded mb-3"
            placeholder="Trigger label"
          />
        </div>
      )}

      {type === "email" && (
        <div>
          <label className="block text-sm font-medium mb-1">Recipient Email</label>
          <input
            value={data.recipient_email || ""}
            onChange={change("recipient_email")}
            className="w-full p-2 border rounded mb-3"
            placeholder="recipient@example.com"
          />

          <label className="block text-sm font-medium mb-1">Subject</label>
          <input
            value={data.subject || ""}
            onChange={change("subject")}
            className="w-full p-2 border rounded mb-3"
            placeholder="Email subject"
          />

          <label className="block text-sm font-medium mb-1">Body (plain or simple HTML)</label>
          <textarea
            value={data.body || ""}
            onChange={(e) => {
              // update body in node data
              onChange("body", e.target.value);
              // also attempt to auto-add placeholders to template area if needed
              // extract placeholders and add missing keys (but don't override user edits)
              const placeholders = extractPlaceholders(e.target.value || "");
              if (placeholders.length > 0) {
                try {
                  const currentParsed = parseTemplateVars(templateRaw);
                  let changed = false;
                  const merged = { ...(currentParsed || {}) };
                  placeholders.forEach((ph) => {
                    if (!(ph in merged)) {
                      merged[ph] = "";
                      changed = true;
                    }
                  });
                  if (changed) {
                    const newRaw = Object.keys(merged).map((k) => `${k}: ${merged[k]}`).join("\n");
                    setTemplateRaw(newRaw);
                    onChange("template_vars", merged);
                    setAutoFilled(true);
                    setTemplateError(null);
                  }
                } catch (_) {}
              }
            }}
            rows={8}
            className="w-full p-2 border rounded mb-3"
            placeholder="Hello {{first_name}}, ..."
          />

          <label className="block text-sm font-medium mb-1">Template Vars (key: value or JSON)</label>
          <textarea
            value={templateRaw}
            onChange={handleTemplateChange}
            rows={6}
            className={`w-full p-2 border rounded mb-1 ${templateError ? "border-red-400" : ""}`}
            placeholder={`first_name: John`}
          />
          {templateError ? (
            <div className="text-sm text-red-500 mb-2">Error: {templateError}</div>
          ) : (
            <div className="text-xs text-gray-500 mb-2">
              Tip: type <code>first_name: John</code> or paste JSON like <code>{"{\"first_name\":\"John\"}"}</code>.
            </div>
          )}
        </div>
      )}

      {type === "delay" && (
        <div>
          <label className="block text-sm font-medium mb-1">Delay</label>
          <div className="flex gap-2 mb-3">
            <input
              type="number"
              min="0"
              value={data.duration ?? 1}
              onChange={(e) => onChange("duration", Number(e.target.value))}
              className="w-24 p-2 border rounded"
            />
            <select
              value={data.unit || "hours"}
              onChange={(e) => onChange("unit", e.target.value)}
              className="p-2 border rounded"
            >
              <option value="minutes">Minutes</option>
              <option value="hours">Hours</option>
              <option value="days">Days</option>
            </select>
          </div>
          <div className="text-xs text-gray-500">
            Use this node to add a wait time before the next node executes.
          </div>
        </div>
      )}

      {type !== "trigger" && type !== "email" && type !== "delay" && (
        <div>
          <label className="block text-sm font-medium mb-1">Label</label>
          <input
            value={data.label || ""}
            onChange={change("label")}
            className="w-full p-2 border rounded mb-3"
            placeholder="Node label"
          />
        </div>
      )}
    </div>
  );
}
