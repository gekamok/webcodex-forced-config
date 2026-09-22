import { useRef, useState, type FormEvent } from "react";
import { desktopApi } from "../../lib/desktop-api";
import type { DesktopState, SettingsTarget } from "../../models/topology";
import type { AcpGlobalSettings } from "../../models/runner-capabilities";
import { useProduct } from "../../i18n/product";
import { useRunnerCapabilitiesText } from "../../i18n/runner-capabilities";
import { WorkspaceDialog } from "../workspace/WorkspaceDialog";

export function CodingAgentGlobalSettingsEditor({ settings, revision, target, onState, onClose }: {
  settings: AcpGlobalSettings | null;
  revision: number;
  target: SettingsTarget;
  onState: (state: DesktopState) => void;
  onClose: () => void;
}) {
  const p = useProduct();
  const r = useRunnerCapabilitiesText();
  const [concurrency, setConcurrency] = useState(settings?.max_concurrent_runs ?? 1);
  const [timeout, setTimeout] = useState(settings?.permission_timeout_secs ?? 5);
  const [model, setModel] = useState(typeof settings?.forced_config?.model === "string" ? settings.forced_config.model : "gpt-6-luna");
  const [effort, setEffort] = useState(typeof settings?.forced_config?.reasoning_effort === "string" ? settings.forced_config.reasoning_effort : "max");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitting = useRef(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting.current) return;
    const forced: Record<string, string | boolean> = { ...(settings?.forced_config ?? {}) };
    delete forced.model;
    delete forced.reasoning_effort;
    if (model.trim()) forced.model = model.trim();
    if (effort) forced.reasoning_effort = effort;
    if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 8 || !Number.isInteger(timeout) || timeout < 1 || timeout > 60 || model.length > 128) {
      setError("invalid_fields");
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      onState(await desktopApi.saveCodingAgentGlobals({
        target,
        expected_revision: revision,
        global_settings: {
          max_concurrent_runs: concurrency,
          permission_timeout_secs: timeout,
          forced_config: forced,
        },
      }));
      onClose();
    } catch (failure) {
      setError(typeof failure === "object" && failure !== null && "code" in failure ? String(failure.code) : "operation_failed");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  return <WorkspaceDialog title={r("globalAcpSettings")} onClose={onClose} busy={busy}>
    <form className="profile-editor" onSubmit={event => void submit(event)} aria-busy={busy}>
      <p className="workspace-notice">{r("globalForcedHelp")}</p>
      <div className="field-group"><label htmlFor="coding-global-model">{r("forcedModel")}</label><input id="coding-global-model" aria-label="Global forced model" value={model} onChange={event => setModel(event.target.value)} maxLength={128} disabled={busy} spellCheck={false} placeholder="gpt-6-luna" /></div>
      <div className="field-group"><label htmlFor="coding-global-effort">{r("forcedReasoning")}</label><select id="coding-global-effort" aria-label="Global forced reasoning effort" value={effort} onChange={event => setEffort(event.target.value)} disabled={busy}><option value="">—</option><option value="low">low</option><option value="medium">medium</option><option value="high">high</option><option value="xhigh">xhigh</option><option value="max">max</option></select></div>
      <div className="mcp-environment-row"><div className="field-group"><label htmlFor="coding-global-concurrency">{r("maxConcurrent")}</label><input id="coding-global-concurrency" type="number" min={1} max={8} value={concurrency} onChange={event => setConcurrency(event.target.valueAsNumber)} required disabled={busy} /></div><div className="field-group"><label htmlFor="coding-global-timeout">{r("permissionTimeout")}</label><input id="coding-global-timeout" type="number" min={1} max={60} value={timeout} onChange={event => setTimeout(event.target.valueAsNumber)} required disabled={busy} /></div></div>
      {error && <p role="alert" className="workspace-notice">{error}</p>}
      <div className="connection-actions"><button className="primary-button" type="submit" aria-label="Save Global ACP Settings" disabled={busy}>{p("save")}</button><button className="secondary-button" type="button" disabled={busy} onClick={onClose}>{p("cancel")}</button></div>
    </form>
  </WorkspaceDialog>;
}
