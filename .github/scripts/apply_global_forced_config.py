from pathlib import Path
import re

ROOT = Path(".")

def read(path):
    return (ROOT / path).read_text()

def write(path, text):
    (ROOT / path).write_text(text)

def rep(path, old, new, count=1):
    text = read(path)
    if old not in text:
        raise SystemExit(f"expected text not found in {path}: {old[:180]!r}")
    write(path, text.replace(old, new, count))

p = "crates/webcodex-runner/src/webcodex_runner/config.rs"
rep(p,
'''pub(crate) struct AcpConfig {
    #[serde(default = "default_acp_max_concurrent_runs")]
    pub(crate) max_concurrent_runs: usize,
    #[serde(default = "default_acp_permission_timeout_secs")]
    pub(crate) permission_timeout_secs: u64,
    #[serde(default)]
    pub(crate) agents: Vec<AcpAgentConfig>,
}''',
'''pub(crate) struct AcpConfig {
    #[serde(default = "default_acp_max_concurrent_runs")]
    pub(crate) max_concurrent_runs: usize,
    #[serde(default = "default_acp_permission_timeout_secs")]
    pub(crate) permission_timeout_secs: u64,
    /// Runner-wide ACP policy applied to every coding-agent session.
    #[serde(default = "default_acp_forced_config")]
    pub(crate) forced_config: BTreeMap<String, CodingAgentConfigValue>,
    #[serde(default)]
    pub(crate) agents: Vec<AcpAgentConfig>,
}''')

rep(p,
'''fn default_acp_permission_timeout_secs() -> u64 {
    DEFAULT_ACP_PERMISSION_TIMEOUT_SECS
}

impl Default for AcpConfig {''',
'''fn default_acp_permission_timeout_secs() -> u64 {
    DEFAULT_ACP_PERMISSION_TIMEOUT_SECS
}

fn default_acp_forced_config() -> BTreeMap<String, CodingAgentConfigValue> {
    BTreeMap::from([
        (
            "model".to_string(),
            CodingAgentConfigValue::String("gpt-6-luna".to_string()),
        ),
        (
            "reasoning_effort".to_string(),
            CodingAgentConfigValue::String("max".to_string()),
        ),
    ])
}

impl Default for AcpConfig {''')

rep(p,
'''        Self {
            max_concurrent_runs: default_acp_max_concurrent_runs(),
            permission_timeout_secs: default_acp_permission_timeout_secs(),
            agents: Vec::new(),
        }''',
'''        Self {
            max_concurrent_runs: default_acp_max_concurrent_runs(),
            permission_timeout_secs: default_acp_permission_timeout_secs(),
            forced_config: default_acp_forced_config(),
            agents: Vec::new(),
        }''')

rep(p,
'''fn validate_acp_config(config: &AcpConfig) -> Result<(), String> {
    use std::collections::HashSet;
    use webcodex_core::coding_agent::{
        validate_provider_id, CODING_AGENT_MAX_CONFIG_KEY_BYTES, CODING_AGENT_MAX_CONFIG_OPTIONS,
        CODING_AGENT_MAX_CONFIG_VALUE_BYTES, CODING_AGENT_MAX_PROVIDERS,
        CODING_AGENT_MAX_PROVIDER_NAME_BYTES,
    };''',
'''fn validate_forced_config_map(
    label: &str,
    forced: &BTreeMap<String, CodingAgentConfigValue>,
) -> Result<(), String> {
    use webcodex_core::coding_agent::{
        CODING_AGENT_MAX_CONFIG_KEY_BYTES, CODING_AGENT_MAX_CONFIG_OPTIONS,
        CODING_AGENT_MAX_CONFIG_VALUE_BYTES,
    };

    if forced.len() > CODING_AGENT_MAX_CONFIG_OPTIONS {
        return Err(format!(
            "{label} may contain at most {CODING_AGENT_MAX_CONFIG_OPTIONS} entries"
        ));
    }
    for (option, value) in forced {
        if option.is_empty()
            || option.len() > CODING_AGENT_MAX_CONFIG_KEY_BYTES
            || option.chars().any(char::is_control)
            || value.serialized_len() > CODING_AGENT_MAX_CONFIG_VALUE_BYTES
        {
            return Err(format!("{label} contains an invalid forced config option"));
        }
        if matches!(value, CodingAgentConfigValue::Integer(_)) {
            return Err(format!("{label} supports only string and boolean values"));
        }
    }
    Ok(())
}

fn validate_acp_config(config: &AcpConfig) -> Result<(), String> {
    use std::collections::HashSet;
    use webcodex_core::coding_agent::{
        validate_provider_id, CODING_AGENT_MAX_CONFIG_KEY_BYTES, CODING_AGENT_MAX_PROVIDERS,
        CODING_AGENT_MAX_PROVIDER_NAME_BYTES,
    };''')

rep(p,
'''    if config.agents.len() > CODING_AGENT_MAX_PROVIDERS {
        return Err(format!(
            "acp.agents may contain at most {CODING_AGENT_MAX_PROVIDERS} entries"
        ));
    }
    let mut ids = HashSet::new();''',
'''    if config.agents.len() > CODING_AGENT_MAX_PROVIDERS {
        return Err(format!(
            "acp.agents may contain at most {CODING_AGENT_MAX_PROVIDERS} entries"
        ));
    }
    validate_forced_config_map("acp.forced_config", &config.forced_config)?;
    let mut ids = HashSet::new();''')

rep(p,
'''        if agent.forced_config.len() > CODING_AGENT_MAX_CONFIG_OPTIONS {
            return Err(format!(
                "ACP agent '{}' forced_config may contain at most {CODING_AGENT_MAX_CONFIG_OPTIONS} entries",
                agent.id
            ));
        }
        for (option, value) in &agent.forced_config {
            if option.is_empty()
                || option.len() > CODING_AGENT_MAX_CONFIG_KEY_BYTES
                || option.chars().any(char::is_control)
                || value.serialized_len() > CODING_AGENT_MAX_CONFIG_VALUE_BYTES
            {
                return Err(format!(
                    "ACP agent '{}' contains an invalid forced config option",
                    agent.id
                ));
            }
            if matches!(value, CodingAgentConfigValue::Integer(_)) {
                return Err(format!(
                    "ACP agent '{}' forced_config supports only string and boolean values",
                    agent.id
                ));
            }
            if config_ids.contains(option.as_str()) {
                return Err(format!(
                    "ACP agent '{}' config options cannot be both allowed and forced",
                    agent.id
                ));
            }
        }''',
'''        validate_forced_config_map(
            &format!("ACP agent '{}' forced_config", agent.id),
            &agent.forced_config,
        )?;
        for option in agent.forced_config.keys() {
            if config_ids.contains(option.as_str()) {
                return Err(format!(
                    "ACP agent '{}' config options cannot be both allowed and forced",
                    agent.id
                ));
            }
        }
        for option in config.forced_config.keys() {
            if config_ids.contains(option.as_str()) {
                return Err(format!(
                    "ACP agent '{}' config options cannot be allowed when forced globally",
                    agent.id
                ));
            }
        }''')

rep(p,
'''    #[test]
    fn acp_forced_config_rejects_allowed_overlap() {''',
'''    #[test]
    fn acp_global_forced_config_defaults_to_luna_max() {
        let config = AcpConfig::default();
        assert_eq!(
            config.forced_config.get("model"),
            Some(&CodingAgentConfigValue::String("gpt-6-luna".to_string()))
        );
        assert_eq!(
            config.forced_config.get("reasoning_effort"),
            Some(&CodingAgentConfigValue::String("max".to_string()))
        );
    }

    #[test]
    fn acp_global_forced_config_rejects_allowed_overlap() {
        let mut config = AcpConfig::default();
        let mut configured = agent();
        configured.allowed_config_options.push("model".to_string());
        config.agents.push(configured);
        assert!(validate_acp_config(&config)
            .unwrap_err()
            .contains("forced globally"));
    }

    #[test]
    fn acp_forced_config_rejects_allowed_overlap() {''')

p = "crates/webcodex-runner/src/webcodex_runner/coding_agent.rs"
rep(p,
'''impl CodingAgentManager {
    pub(crate) fn new(''',
'''fn effective_provider_config(config: &AcpConfig, provider: &AcpAgentConfig) -> AcpAgentConfig {
    let mut effective = provider.clone();
    for (key, value) in &config.forced_config {
        effective.forced_config.insert(key.clone(), value.clone());
    }
    effective
}

impl CodingAgentManager {
    pub(crate) fn new(''')

rep(p,
'''                Arc::new(ProviderEntry {
                    config: provider.clone(),
                    instance_id: format!("acp_{}", Uuid::new_v4().simple()),
                }),''',
'''                Arc::new(ProviderEntry {
                    config: effective_provider_config(config, provider),
                    instance_id: format!("acp_{}", Uuid::new_v4().simple()),
                }),''',
count=2)

rep(p,
'''    fn force_luna_max(cfg: &mut AcpConfig) {
        cfg.agents[0].forced_config = BTreeMap::from([''',
'''    fn force_luna_max(cfg: &mut AcpConfig) {
        cfg.forced_config = BTreeMap::from([''')

rep(p,
'''        AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 1,
            agents: vec![AcpAgentConfig {''',
'''        AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 1,
            forced_config: BTreeMap::new(),
            agents: vec![AcpAgentConfig {''')

text = read(p)
text = text.replace(
'''        let cfg = AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 3,
            agents:''',
'''        let cfg = AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 3,
            forced_config: BTreeMap::new(),
            agents:''')
text = text.replace(
'''        let cfg = AcpConfig {
            max_concurrent_runs: manager.max_concurrent_runs,
            permission_timeout_secs: 1,
            agents:''',
'''        let cfg = AcpConfig {
            max_concurrent_runs: manager.max_concurrent_runs,
            permission_timeout_secs: 1,
            forced_config: BTreeMap::new(),
            agents:''')
write(p, text)

rep(p,
'''    #[test]
    #[cfg(unix)]
    fn forced_config_is_applied_before_prompt() {''',
'''    #[test]
    #[cfg(unix)]
    fn global_forced_config_overrides_provider_for_every_session() {
        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "forced_configs");
        let mut cfg = fake_config(exe, args);
        cfg.agents[0].forced_config.insert(
            "model".to_string(),
            CodingAgentConfigValue::String("default-model".to_string()),
        );
        force_luna_max(&mut cfg);
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();
        let run = "wc_agent_run_globalforced01";
        assert!(manager
            .handle(
                start_request(&manager, &root, run, BTreeMap::new()),
                &projects,
            )
            .error
            .is_none());
        let terminal = wait_for_snapshot(&manager, run, |snapshot| snapshot.state.terminal());
        assert_eq!(terminal.state, CodingAgentRunState::Completed);
        let provider = manager.providers.values().next().unwrap();
        assert_eq!(
            provider.config.forced_config.get("model"),
            Some(&CodingAgentConfigValue::String("gpt-6-luna".to_string()))
        );
        assert_eq!(
            provider.config.forced_config.get("reasoning_effort"),
            Some(&CodingAgentConfigValue::String("max".to_string()))
        );
    }

    #[test]
    #[cfg(unix)]
    fn forced_config_is_applied_before_prompt() {''')

p = "apps/desktop/src-tauri/src/coding_agents.rs"
rep(p,
'''pub struct AcpGlobalSettings {
    pub max_concurrent_runs: usize,
    pub permission_timeout_secs: u64,
}''',
'''pub struct AcpGlobalSettings {
    pub max_concurrent_runs: usize,
    pub permission_timeout_secs: u64,
    #[serde(default = "default_global_forced_config")]
    pub forced_config: BTreeMap<String, CodingAgentConfigValue>,
}

fn default_global_forced_config() -> BTreeMap<String, CodingAgentConfigValue> {
    BTreeMap::from([
        (
            "model".to_string(),
            CodingAgentConfigValue::String("gpt-6-luna".to_string()),
        ),
        (
            "reasoning_effort".to_string(),
            CodingAgentConfigValue::String("max".to_string()),
        ),
    ])
}

impl Default for AcpGlobalSettings {
    fn default() -> Self {
        Self {
            max_concurrent_runs: 1,
            permission_timeout_secs: 5,
            forced_config: default_global_forced_config(),
        }
    }
}''')

rep(p,
'''pub struct CodingAgentRemove {
    pub target: crate::webcodex::settings::SettingsTarget,
    pub expected_revision: u64,
    pub provider_id: String,
}''',
'''pub struct CodingAgentRemove {
    pub target: crate::webcodex::settings::SettingsTarget,
    pub expected_revision: u64,
    pub provider_id: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CodingAgentGlobalsUpdate {
    pub target: crate::webcodex::settings::SettingsTarget,
    pub expected_revision: u64,
    pub global_settings: AcpGlobalSettings,
}''')

rep(p,
'''    pub fn stage_remove(&mut self, id: &str, revision: u64) -> DesktopResult<()> {
        self.check_revision(revision)?;''',
'''    pub fn stage_global_settings(
        &mut self,
        settings: AcpGlobalSettings,
        revision: u64,
    ) -> DesktopResult<()> {
        self.check_revision(revision)?;
        validate_global_settings(&settings)?;
        let mut next = self.manifest.clone();
        next.global_settings = Some(settings);
        next.revision = next.revision.checked_add(1).ok_or_else(invalid)?;
        validate_manifest(&next)?;
        self.manifest = next;
        Ok(())
    }

    pub fn stage_remove(&mut self, id: &str, revision: u64) -> DesktopResult<()> {
        self.check_revision(revision)?;''')

rep(p,
'''fn validate_profile(profile: &CodingAgentProfile) -> DesktopResult<()> {''',
'''fn validate_desktop_forced_config(
    forced: &BTreeMap<String, CodingAgentConfigValue>,
) -> DesktopResult<()> {
    if forced.len() > CODING_AGENT_MAX_CONFIG_OPTIONS {
        return Err(invalid());
    }
    for (key, value) in forced {
        if key.is_empty()
            || key.len() > CODING_AGENT_MAX_CONFIG_KEY_BYTES
            || key.chars().any(char::is_control)
            || value.serialized_len() > CODING_AGENT_MAX_CONFIG_VALUE_BYTES
            || matches!(value, CodingAgentConfigValue::Integer(_))
        {
            return Err(invalid());
        }
    }
    Ok(())
}

fn validate_global_settings(settings: &AcpGlobalSettings) -> DesktopResult<()> {
    if !(1..=8).contains(&settings.max_concurrent_runs)
        || !(1..=60).contains(&settings.permission_timeout_secs)
    {
        return Err(invalid());
    }
    validate_desktop_forced_config(&settings.forced_config)
}

fn validate_profile(profile: &CodingAgentProfile) -> DesktopResult<()> {''')

rep(p,
'''    for (key, value) in &profile.forced_config {
        if key.is_empty()
            || key.len() > CODING_AGENT_MAX_CONFIG_KEY_BYTES
            || key.chars().any(char::is_control)
            || value.serialized_len() > CODING_AGENT_MAX_CONFIG_VALUE_BYTES
            || matches!(value, CodingAgentConfigValue::Integer(_))
            || options.contains(key)
        {
            return Err(invalid());
        }
    }
    Ok(())''',
'''    validate_desktop_forced_config(&profile.forced_config)?;
    if profile
        .forced_config
        .keys()
        .any(|key| options.contains(key))
    {
        return Err(invalid());
    }
    Ok(())''')

rep(p,
'''    if let Some(settings) = &manifest.global_settings {
        if !(1..=8).contains(&settings.max_concurrent_runs)
            || !(1..=60).contains(&settings.permission_timeout_secs)
        {
            return Err(invalid());
        }
    }''',
'''    if let Some(settings) = &manifest.global_settings {
        validate_global_settings(settings)?;
    }''')

p = "apps/desktop/src-tauri/src/webcodex/settings/acp.rs"
rep(p,
'''        set(
            acp,
            "permission_timeout_secs",
            (settings.permission_timeout_secs as i64).into(),
        );
    }''',
'''        set(
            acp,
            "permission_timeout_secs",
            (settings.permission_timeout_secs as i64).into(),
        );
        let mut forced = InlineTable::new();
        for (key, value) in &settings.forced_config {
            match value {
                CodingAgentConfigValue::String(value) => {
                    forced.insert(key, Value::from(value.as_str()));
                }
                CodingAgentConfigValue::Bool(value) => {
                    forced.insert(key, Value::from(*value));
                }
                CodingAgentConfigValue::Integer(_) => return Err(error()),
            }
        }
        set(acp, "forced_config", forced.into());
    }''')

p = "apps/desktop/src-tauri/src/state/coding_agents.rs"
rep(p,
'use crate::coding_agents::{CodingAgentRemove, CodingAgentStore, CodingAgentUpdate};',
'use crate::coding_agents::{CodingAgentGlobalsUpdate, CodingAgentRemove, CodingAgentStore, CodingAgentUpdate};')
rep(p,
'''    pub async fn remove_coding_agent(
        &self,
        request: CodingAgentRemove,
    ) -> DesktopResult<DesktopStateSnapshot> {''',
'''    pub async fn save_coding_agent_globals(
        &self,
        request: CodingAgentGlobalsUpdate,
    ) -> DesktopResult<DesktopStateSnapshot> {
        self.mutate_coding_agents(request.target.clone(), move |store| {
            store.stage_global_settings(request.global_settings, request.expected_revision)
        })
        .await
    }

    pub async fn remove_coding_agent(
        &self,
        request: CodingAgentRemove,
    ) -> DesktopResult<DesktopStateSnapshot> {''')

p = "apps/desktop/src-tauri/src/commands/mod.rs"
rep(p,
'''#[tauri::command]
pub async fn remove_coding_agent(''',
'''#[tauri::command]
pub async fn save_coding_agent_globals(
    app: AppHandle,
    state: State<'_, AppState>,
    request: crate::coding_agents::CodingAgentGlobalsUpdate,
) -> DesktopResult<DesktopStateSnapshot> {
    project_state_result(&app, state.save_coding_agent_globals(request).await)
}

#[tauri::command]
pub async fn remove_coding_agent(''')

p = "apps/desktop/src-tauri/src/lib.rs"
rep(p,
'''            commands::save_coding_agent,
            commands::remove_coding_agent,''',
'''            commands::save_coding_agent,
            commands::save_coding_agent_globals,
            commands::remove_coding_agent,''')

p = "apps/desktop/src/models/runner-capabilities.ts"
rep(p,
'''export interface AcpGlobalSettings { max_concurrent_runs: number; permission_timeout_secs: number }''',
'''export interface AcpGlobalSettings {
  max_concurrent_runs: number;
  permission_timeout_secs: number;
  forced_config: Record<string, string | boolean>;
}''')
rep(p,
'''export interface CodingAgentRequest {
  target: SettingsTarget;
  expected_revision: number;
  previous_id: string | null;
  profile: CodingAgentProfile;
  global_settings: AcpGlobalSettings | null;
}''',
'''export interface CodingAgentRequest {
  target: SettingsTarget;
  expected_revision: number;
  previous_id: string | null;
  profile: CodingAgentProfile;
  global_settings: AcpGlobalSettings | null;
}
export interface CodingAgentGlobalsRequest {
  target: SettingsTarget;
  expected_revision: number;
  global_settings: AcpGlobalSettings;
}''')

p = "apps/desktop/src/lib/desktop-api.ts"
rep(p,
'import type { CodingAgentRequest, SshRegisterRequest, SshResourcesSnapshot, SshMutationResult, RunnerCapabilityAuthorizationSnapshot } from "../models/runner-capabilities";',
'import type { CodingAgentGlobalsRequest, CodingAgentRequest, SshRegisterRequest, SshResourcesSnapshot, SshMutationResult, RunnerCapabilityAuthorizationSnapshot } from "../models/runner-capabilities";')
rep(p,
'''  saveCodingAgent: (request: CodingAgentRequest) => invoke<DesktopState>("save_coding_agent", { request }),
  removeCodingAgent:''',
'''  saveCodingAgent: (request: CodingAgentRequest) => invoke<DesktopState>("save_coding_agent", { request }),
  saveCodingAgentGlobals: (request: CodingAgentGlobalsRequest) => invoke<DesktopState>("save_coding_agent_globals", { request }),
  removeCodingAgent:''')

p = "apps/desktop/src/features/extensions/CodingAgentEditor.tsx"
text = read(p)
text = re.sub(
    r'''  const \[forcedModel, setForcedModel\] = useState\([\s\S]*?  const \[mapping, setMapping\]''',
    '''  const [mapping, setMapping]''',
    text,
    count=1,
)
text = re.sub(
    r'''  const \[manageGlobals, setManageGlobals\][\s\S]*?  const \[busy, setBusy\]''',
    '''  const [busy, setBusy]''',
    text,
    count=1,
)
text = re.sub(
    r'''      const forced: Record<string, string \| boolean> = \{ \.\.\.\(profile\?\.forced_config \?\? \{\}\) \};[\s\S]*?      const seen = new Set<string>\(\);''',
    '''      const seen = new Set<string>();''',
    text,
    count=1,
)
old = '''        profile: { provider_id: id.trim(), name: name.trim(), executable: executable.trim(), args: parsedArgs, enabled, env_from_env: Object.fromEntries(env), allowed_config_options: allowed, forced_config: forced },
        global_settings: manageGlobals ? { max_concurrent_runs: concurrency, permission_timeout_secs: timeout } : null };'''
new = '''        profile: { provider_id: id.trim(), name: name.trim(), executable: executable.trim(), args: parsedArgs, enabled, env_from_env: Object.fromEntries(env), allowed_config_options: allowed, forced_config: profile?.forced_config ?? {} },
        global_settings: globals };'''
if old not in text:
    raise SystemExit("CodingAgentEditor request block not found")
text = text.replace(old, new, 1)
text = re.sub(
    r'''        <div className="field-group"><label htmlFor="coding-agent-forced-model">[\s\S]*?\{manageGlobals && <div className="mcp-environment-row">[\s\S]*?</div>\}\n''',
    '',
    text,
    count=1,
)
write(p, text)

global_editor = '''import { useRef, useState, type FormEvent } from "react";
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
'''
write("apps/desktop/src/features/extensions/CodingAgentGlobalSettingsEditor.tsx", global_editor)

p = "apps/desktop/src/features/extensions/CodingAgentsPanel.tsx"
rep(p,
'import { CodingAgentEditor } from "./CodingAgentEditor";',
'import { CodingAgentEditor } from "./CodingAgentEditor";\nimport { CodingAgentGlobalSettingsEditor } from "./CodingAgentGlobalSettingsEditor";')
rep(p,
'''  const [editor, setEditor] = useState<{ profile: CodingAgentProfile | null; revision: number; target: SettingsTarget } | null>(null);
  const [deleting,''',
'''  const [editor, setEditor] = useState<{ profile: CodingAgentProfile | null; revision: number; target: SettingsTarget } | null>(null);
  const [globalEditor, setGlobalEditor] = useState(false);
  const [deleting,''')
rep(p,
'''    <div className="extension-toolbar"><button type="button" className="primary-button" aria-label="Add Coding Agent" disabled={disabled || !settings || configured.config_error} onClick={() => settings && setEditor({ profile: null, revision: configured.revision, target: settings.target })}>{r("addCodingAgent")}</button><button type="button" className="secondary-button" aria-label="Refresh Coding Agents" disabled={disabled || loading} onClick={refresh}>{p("refresh")}</button></div>
    <p className="workspace-notice">{r("agentHelp")}</p>''',
'''    <div className="extension-toolbar"><button type="button" className="primary-button" aria-label="Global ACP Settings" disabled={disabled || !settings || configured.config_error} onClick={() => setGlobalEditor(true)}>{r("globalAcpSettings")}</button><button type="button" className="secondary-button" aria-label="Add Coding Agent" disabled={disabled || !settings || configured.config_error} onClick={() => settings && setEditor({ profile: null, revision: configured.revision, target: settings.target })}>{r("addCodingAgent")}</button><button type="button" className="secondary-button" aria-label="Refresh Coding Agents" disabled={disabled || loading} onClick={refresh}>{p("refresh")}</button></div>
    <p className="workspace-notice">{r("agentHelp")}</p>
    <p className="workspace-notice">{r("globalPolicySummary")}: <code>{String(configured.global_settings?.forced_config?.model ?? "gpt-6-luna")}</code> · <code>{String(configured.global_settings?.forced_config?.reasoning_effort ?? "max")}</code></p>''')
rep(p,
'''    {editor && <CodingAgentEditor profile={editor.profile} revision={editor.revision} target={editor.target} globals={configured.global_settings} onState={onState} onClose={() => setEditor(null)} />}
    {deleting &&''',
'''    {editor && <CodingAgentEditor profile={editor.profile} revision={editor.revision} target={editor.target} globals={configured.global_settings} onState={onState} onClose={() => setEditor(null)} />}
    {globalEditor && settings && <CodingAgentGlobalSettingsEditor settings={configured.global_settings} revision={configured.revision} target={settings.target} onState={onState} onClose={() => setGlobalEditor(false)} />}
    {deleting &&''')

p = "apps/desktop/src/i18n/runner-capabilities.ts"
rep(p,
'''  forcedHelp: ["Runner policy: callers cannot override these values. They are validated against the provider's live ACP options before prompt dispatch.", "Runner 策略：调用方不能覆盖这些值；发送 Prompt 前会根据 Provider 实时 ACP 选项校验。", "Runner-Richtlinie: Aufrufer können diese Werte nicht überschreiben; vor dem Prompt werden sie gegen die Live-ACP-Optionen geprüft.", "Politique Runner : l’appelant ne peut pas remplacer ces valeurs ; elles sont validées avec les options ACP actives avant le prompt.", "Runner ポリシーです。呼び出し側は上書きできず、Prompt 送信前に Provider の実際の ACP オプションで検証されます。", "Runner 정책입니다. 호출자가 덮어쓸 수 없으며 Prompt 전송 전에 Provider의 실제 ACP 옵션으로 검증됩니다."],''',
'''  forcedHelp: ["Runner policy: callers cannot override these values. They are validated against the provider's live ACP options before prompt dispatch.", "Runner 策略：调用方不能覆盖这些值；发送 Prompt 前会根据 Provider 实时 ACP 选项校验。", "Runner-Richtlinie: Aufrufer können diese Werte nicht überschreiben; vor dem Prompt werden sie gegen die Live-ACP-Optionen geprüft.", "Politique Runner : l’appelant ne peut pas remplacer ces valeurs ; elles sont validées avec les options ACP actives avant le prompt.", "Runner ポリシーです。呼び出し側は上書きできず、Prompt 送信前に Provider の実際の ACP オプションで検証されます。", "Runner 정책입니다. 호출자가 덮어쓸 수 없으며 Prompt 전송 전에 Provider의 실제 ACP 옵션으로 검증됩니다."],
  globalAcpSettings: ["Global ACP Settings", "全局 ACP 设置", "Globale ACP-Einstellungen", "Paramètres ACP globaux", "グローバル ACP 設定", "전역 ACP 설정"],
  globalPolicySummary: ["Global forced policy", "全局强制策略", "Globale erzwungene Richtlinie", "Politique globale imposée", "グローバル強制ポリシー", "전역 강제 정책"],
  globalForcedHelp: ["Applies to every Coding Agent session on this Runner. Global values override provider-level compatibility settings and callers cannot override them. Native Codex subagents inherit the parent session model and reasoning effort.", "应用于此 Runner 的每个 Coding Agent 会话。全局值覆盖 Provider 级兼容设置，调用方不能覆盖；native Codex 子 Agent 继承父会话的模型和推理强度。", "Gilt für jede Coding-Agent-Sitzung dieses Runners. Globale Werte überschreiben Provider-Einstellungen und können vom Aufrufer nicht geändert werden.", "S’applique à chaque session Coding Agent de ce Runner. Les valeurs globales remplacent les réglages Provider et ne peuvent pas être modifiées par l’appelant.", "この Runner のすべての Coding Agent セッションに適用されます。グローバル値は Provider 設定より優先され、呼び出し側は上書きできません。", "이 Runner의 모든 Coding Agent 세션에 적용됩니다. 전역 값은 Provider 설정보다 우선하며 호출자가 덮어쓸 수 없습니다."],''')

p = "apps/desktop/src/features/RunnerCapabilities.test.tsx"
text = read(p)
text = text.replace(
'const api = vi.hoisted(() => ({ saveCodingAgent: vi.fn(),',
'const api = vi.hoisted(() => ({ saveCodingAgent: vi.fn(), saveCodingAgentGlobals: vi.fn(),')
marker = '''  it("never invents Active from desired state, another Runner or a stale provider name", async () => {'''
test = '''  it("saves GPT-6 Luna max as Runner-global ACP policy", async () => {
    const saved = state();
    saved.coding_agents = { ...EMPTY_CODING_AGENTS, revision: 1, global_settings: { max_concurrent_runs: 1, permission_timeout_secs: 5, forced_config: { model: "gpt-6-luna", reasoning_effort: "max" } }, restart_required: true };
    api.saveCodingAgentGlobals.mockResolvedValue(saved);
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Global ACP Settings" }));
    const dialog = screen.getByRole("dialog", { name: "Global ACP Settings" });
    expect(within(dialog).getByLabelText("Global forced model")).toHaveValue("gpt-6-luna");
    expect(within(dialog).getByLabelText("Global forced reasoning effort")).toHaveValue("max");
    fireEvent.click(within(dialog).getByRole("button", { name: "Save Global ACP Settings" }));
    await waitFor(() => expect(api.saveCodingAgentGlobals).toHaveBeenCalledWith(expect.objectContaining({
      target,
      expected_revision: 0,
      global_settings: expect.objectContaining({
        forced_config: { model: "gpt-6-luna", reasoning_effort: "max" },
      }),
    })));
  });

  it("never invents Active from desired state, another Runner or a stale provider name", async () => {'''
if marker not in text:
    raise SystemExit("frontend test insertion marker missing")
text = text.replace(marker, test, 1)
write(p, text)

p = "apps/desktop/src-tauri/src/coding_agents/tests.rs"
rep(p,
'''        update.global_settings = Some(AcpGlobalSettings {
            max_concurrent_runs: runs,
            permission_timeout_secs: timeout,
        });''',
'''        update.global_settings = Some(AcpGlobalSettings {
            max_concurrent_runs: runs,
            permission_timeout_secs: timeout,
            forced_config: default_global_forced_config(),
        });''')
text = read(p)
idx = text.find("#[test]")
if idx < 0:
    raise SystemExit("backend test marker missing")
newtest = '''#[test]
fn global_settings_default_to_gpt6_luna_max() {
    let settings = AcpGlobalSettings::default();
    assert_eq!(
        settings.forced_config.get("model"),
        Some(&CodingAgentConfigValue::String("gpt-6-luna".into()))
    );
    assert_eq!(
        settings.forced_config.get("reasoning_effort"),
        Some(&CodingAgentConfigValue::String("max".into()))
    );
}

'''
text = text[:idx] + newtest + text[idx:]
write(p, text)

p = "deploy/webcodex-runner.toml.example"
rep(p,
'''# [acp]
# max_concurrent_runs = 1
#
# [[acp.agents]]''',
'''# [acp]
# max_concurrent_runs = 1
#
# Runner-global policy. This fork defaults to GPT-6 Luna + max when omitted.
# [acp.forced_config]
# model = "gpt-6-luna"
# reasoning_effort = "max"
#
# [[acp.agents]]''')
text = read(p)
text = re.sub(
r'''# # Runner-local administrator policy\. These values are validated against the
# # provider's live advertised options and re-verified before session/prompt\.
# # A conflicting remote value fails closed; there is no fallback\.
# # The values below are examples and must actually be advertised by your ACP
# # provider/session or the CodingAgentRun will fail before prompt dispatch\.
# \[acp\.agents\.forced_config\]
# model = "gpt-6-luna"
# reasoning_effort = "max"
''',
'''# Optional provider-specific compatibility policy remains supported.
# The Runner-global acp.forced_config wins on duplicate keys.
# [acp.agents.forced_config]
# mode = "read-only"
''',
text,
count=1)
write(p, text)

print("global forced-config patch applied")
