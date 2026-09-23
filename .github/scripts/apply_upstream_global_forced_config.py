from pathlib import Path

ROOT = Path(".")

def read(path):
    return (ROOT / path).read_text()

def write(path, text):
    (ROOT / path).write_text(text)

def rep(path, old, new, count=1):
    text = read(path)
    if old not in text:
        raise SystemExit(f"expected text not found in {path}: {old[:160]!r}")
    write(path, text.replace(old, new, count))

# ---------------------------------------------------------------------------
# Runner config: one global, neutral forced_config map.
# ---------------------------------------------------------------------------
p = "crates/webcodex-runner/src/webcodex_runner/config.rs"
rep(
    p,
    "use std::sync::{Arc, Mutex, RwLock, Weak};\n",
    "use std::sync::{Arc, Mutex, RwLock, Weak};\nuse webcodex_core::coding_agent::CodingAgentConfigValue;\n",
)

rep(
    p,
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
    /// Runner-owned admission policy applied to every ACP Coding Agent session.
    /// The upstream default is intentionally empty and provider-neutral.
    #[serde(default)]
    pub(crate) forced_config: BTreeMap<String, CodingAgentConfigValue>,
    #[serde(default)]
    pub(crate) agents: Vec<AcpAgentConfig>,
}''',
)

rep(
    p,
'''        Self {
            max_concurrent_runs: default_acp_max_concurrent_runs(),
            permission_timeout_secs: default_acp_permission_timeout_secs(),
            agents: Vec::new(),
        }''',
'''        Self {
            max_concurrent_runs: default_acp_max_concurrent_runs(),
            permission_timeout_secs: default_acp_permission_timeout_secs(),
            forced_config: BTreeMap::new(),
            agents: Vec::new(),
        }''',
)

rep(
    p,
'''    use webcodex_core::coding_agent::{
        validate_provider_id, CODING_AGENT_MAX_CONFIG_KEY_BYTES, CODING_AGENT_MAX_PROVIDERS,
        CODING_AGENT_MAX_PROVIDER_NAME_BYTES,
    };''',
'''    use webcodex_core::coding_agent::{
        validate_provider_id, CODING_AGENT_MAX_CONFIG_KEY_BYTES, CODING_AGENT_MAX_CONFIG_OPTIONS,
        CODING_AGENT_MAX_CONFIG_VALUE_BYTES, CODING_AGENT_MAX_PROVIDERS,
        CODING_AGENT_MAX_PROVIDER_NAME_BYTES,
    };''',
)

rep(
    p,
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
    if config.forced_config.len() > CODING_AGENT_MAX_CONFIG_OPTIONS {
        return Err(format!(
            "acp.forced_config may contain at most {CODING_AGENT_MAX_CONFIG_OPTIONS} entries"
        ));
    }
    for (option, value) in &config.forced_config {
        if option.is_empty()
            || option.len() > CODING_AGENT_MAX_CONFIG_KEY_BYTES
            || option.chars().any(char::is_control)
            || value.serialized_len() > CODING_AGENT_MAX_CONFIG_VALUE_BYTES
        {
            return Err("acp.forced_config contains an invalid option".to_string());
        }
        if matches!(value, CodingAgentConfigValue::Integer(_)) {
            return Err(
                "acp.forced_config supports only string/select and boolean values".to_string(),
            );
        }
    }
    let mut ids = HashSet::new();''',
)

rep(
    p,
r'''        for option in &agent.allowed_config_options {
            if option.is_empty()
                || option.len() > CODING_AGENT_MAX_CONFIG_KEY_BYTES
                || option.contains(['\0', '\r', '\n'])
                || !config_ids.insert(option.as_str())
            {
                return Err(format!(
                    "ACP agent '{}' contains an invalid or duplicate allowed config option",
                    agent.id
                ));
            }
        }
    }
    Ok(())''',
r'''        for option in &agent.allowed_config_options {
            if option.is_empty()
                || option.len() > CODING_AGENT_MAX_CONFIG_KEY_BYTES
                || option.contains(['\0', '\r', '\n'])
                || !config_ids.insert(option.as_str())
            {
                return Err(format!(
                    "ACP agent '{}' contains an invalid or duplicate allowed config option",
                    agent.id
                ));
            }
        }
        if config
            .forced_config
            .keys()
            .any(|option| config_ids.contains(option.as_str()))
        {
            return Err(format!(
                "ACP agent '{}' cannot allow an option that is forced globally",
                agent.id
            ));
        }
    }
    Ok(())''',
)

# Add focused config-validation tests inside acp_config_tests.
marker = '''    #[test]
    fn acp_env_mapping_rejects_webcodex_pat() {'''
insert = '''    #[test]
    fn acp_global_forced_config_is_empty_by_default() {
        assert!(AcpConfig::default().forced_config.is_empty());
    }

    #[test]
    fn acp_global_forced_config_rejects_allowed_overlap() {
        let mut configured = agent();
        configured.allowed_config_options.push("model".to_string());
        let mut config = AcpConfig {
            agents: vec![configured],
            ..AcpConfig::default()
        };
        config.forced_config.insert(
            "model".to_string(),
            CodingAgentConfigValue::String("policy-model".to_string()),
        );
        assert!(validate_acp_config(&config)
            .unwrap_err()
            .contains("forced globally"));
    }

    #[test]
    fn acp_global_forced_config_rejects_integer_values() {
        let mut config = AcpConfig::default();
        config
            .forced_config
            .insert("integer-option".to_string(), CodingAgentConfigValue::Integer(7));
        assert!(validate_acp_config(&config)
            .unwrap_err()
            .contains("string/select and boolean"));
    }

    #[test]
    fn acp_env_mapping_rejects_webcodex_pat() {'''
rep(p, marker, insert)

# ---------------------------------------------------------------------------
# Runtime: enforce global policy for every provider session.
# ---------------------------------------------------------------------------
p = "crates/webcodex-runner/src/webcodex_runner/coding_agent.rs"

rep(
    p,
'''pub(crate) struct CodingAgentManager {
    client_id: String,
    providers: BTreeMap<String, Arc<ProviderEntry>>,
    max_concurrent_runs: usize,''',
'''pub(crate) struct CodingAgentManager {
    client_id: String,
    providers: BTreeMap<String, Arc<ProviderEntry>>,
    forced_config: BTreeMap<String, CodingAgentConfigValue>,
    max_concurrent_runs: usize,''',
)

# Two constructors.
text = read(p)
old = '''            client_id: client_id.to_string(),
            providers,
            max_concurrent_runs: config.max_concurrent_runs,'''
new = '''            client_id: client_id.to_string(),
            providers,
            forced_config: config.forced_config.clone(),
            max_concurrent_runs: config.max_concurrent_runs,'''
if old not in text:
    raise SystemExit("production manager constructor marker missing")
text = text.replace(old, new, 1)
old = '''            client_id: "test".to_string(),
            providers,
            max_concurrent_runs: config.max_concurrent_runs,'''
new = '''            client_id: "test".to_string(),
            providers,
            forced_config: config.forced_config.clone(),
            max_concurrent_runs: config.max_concurrent_runs,'''
if old not in text:
    raise SystemExit("test manager constructor marker missing")
text = text.replace(old, new, 1)
write(p, text)

# Shared pre-prompt config application helper. This keeps forced and caller
# config on the same live ACP validation/reflection path.
helper = r'''
    #[allow(clippy::too_many_arguments)]
    fn apply_pre_prompt_config_option(
        &self,
        run_id: &str,
        entry: &Arc<RunEntry>,
        child: &mut ManagedChild,
        outbound: &mut AcpOutboundWriter,
        rx: &Receiver<ReaderEvent>,
        run_deadline: Instant,
        session_id: &str,
        next_id: &mut u64,
        advertised: &mut Vec<SessionConfigOption>,
        key: &str,
        value: &CodingAgentConfigValue,
        forced: bool,
    ) -> bool {
        if self.pre_prompt_should_stop(run_id, entry, run_deadline) {
            self.terminate_run_io(child, outbound);
            return false;
        }
        if !advertised.iter().any(|option| option.id.to_string() == key) {
            self.setup_failure(
                run_id,
                entry,
                if forced {
                    "coding_agent_forced_config_not_advertised"
                } else {
                    "coding_agent_config_invalid"
                },
                if forced {
                    "Runner-enforced ACP config option is not advertised by provider"
                } else {
                    "ACP config override is not currently advertised/legal"
                },
            );
            self.terminate_run_io(child, outbound);
            return false;
        }
        if !config_override_is_valid(advertised, key, value) {
            self.setup_failure(
                run_id,
                entry,
                if forced {
                    "coding_agent_forced_config_invalid"
                } else {
                    "coding_agent_config_invalid"
                },
                if forced {
                    "Runner-enforced ACP config value is not currently legal for provider"
                } else {
                    "ACP config override is not currently advertised/legal"
                },
            );
            self.terminate_run_io(child, outbound);
            return false;
        }

        let config_id = *next_id;
        *next_id += 1;
        let params = match config_params(session_id, key, value) {
            Some(params) => params,
            None => {
                self.setup_failure(
                    run_id,
                    entry,
                    if forced {
                        "coding_agent_forced_config_invalid"
                    } else {
                        "coding_agent_config_invalid"
                    },
                    if forced {
                        "Runner-enforced ACP config value type is unsupported by stable v1"
                    } else {
                        "ACP config value type is unsupported by stable v1"
                    },
                );
                self.terminate_run_io(child, outbound);
                return false;
            }
        };
        if !self.write_pre_prompt_frame(
            run_id,
            entry,
            child,
            outbound,
            request_frame(config_id, "session/set_config_option", params),
            run_deadline,
            if forced {
                "coding_agent_forced_config_write_failed"
            } else {
                "coding_agent_config_write_failed"
            },
            if forced {
                "failed to write Runner-enforced session/set_config_option"
            } else {
                "failed to write session/set_config_option"
            },
        ) {
            return false;
        }
        let Some(config_wait) = bounded_setup_wait(run_deadline) else {
            self.setup_timeout(run_id, entry);
            self.terminate_run_io(child, outbound);
            return false;
        };
        let result = match wait_response(rx, config_id, config_wait, Some(&entry.cancel_requested))
        {
            Ok(result) => result,
            Err(error) => {
                if !self.pre_prompt_should_stop(run_id, entry, run_deadline) {
                    self.setup_failure(
                        run_id,
                        entry,
                        if forced {
                            "coding_agent_forced_config_failed"
                        } else {
                            "coding_agent_config_failed"
                        },
                        &error,
                    );
                }
                self.terminate_run_io(child, outbound);
                return false;
            }
        };
        if self.pre_prompt_should_stop(run_id, entry, run_deadline) {
            self.terminate_run_io(child, outbound);
            return false;
        }
        let refreshed: SetSessionConfigOptionResponse = match serde_json::from_value(result) {
            Ok(result) => result,
            Err(_) => {
                self.setup_failure(
                    run_id,
                    entry,
                    if forced {
                        "coding_agent_forced_config_invalid_response"
                    } else {
                        "coding_agent_config_invalid_response"
                    },
                    "invalid refreshed ACP config options",
                );
                self.terminate_run_io(child, outbound);
                return false;
            }
        };
        *advertised = refreshed.config_options;
        if !config_override_is_current(advertised, key, value) {
            self.setup_failure(
                run_id,
                entry,
                if forced {
                    "coding_agent_forced_config_not_applied"
                } else {
                    "coding_agent_config_not_applied"
                },
                if forced {
                    "Runner-enforced ACP config was not reflected by provider"
                } else {
                    "ACP config override was not reflected by provider"
                },
            );
            self.terminate_run_io(child, outbound);
            return false;
        }
        true
    }

'''
text = read(p)
needle = "    fn terminate_run_io(&self, child: &mut ManagedChild, outbound: &mut AcpOutboundWriter) {"
if needle not in text:
    raise SystemExit("terminate_run_io marker missing")
text = text.replace(needle, helper + needle, 1)
write(p, text)

# Replace the existing caller-only config loop after session/new with global
# forced policy, caller config, re-assertion, and a final current-value check.
text = read(p)
anchor = "        let session_id = new_session.session_id.to_string();\n        let mut advertised = new_session.config_options.unwrap_or_default();"
a = text.index(anchor)
start = text.index("\n        for (key, value) in &request.config {", a)
end = text.index("\n        #[cfg(test)]", start)
new_block = r'''
        // Runner-owned global forced config is admission policy, not a
        // best-effort preference. Conflicting caller input fails before prompt.
        for (key, value) in &request.config {
            if let Some(forced_value) = self.forced_config.get(key) {
                if value != forced_value {
                    self.setup_failure(
                        &request.run_id,
                        &entry,
                        "coding_agent_forced_config_conflict",
                        "caller ACP config conflicts with Runner-enforced policy",
                    );
                    self.terminate_run_io(&mut child, &mut outbound);
                    return;
                }
            }
        }

        for (key, value) in &self.forced_config {
            if !self.apply_pre_prompt_config_option(
                &request.run_id,
                &entry,
                &mut child,
                &mut outbound,
                &rx,
                run_deadline,
                &session_id,
                &mut next_id,
                &mut advertised,
                key,
                value,
                true,
            ) {
                return;
            }
        }

        for (key, value) in &request.config {
            // Exact repetition of globally forced policy is accepted but is not
            // a caller override and is already active.
            if self.forced_config.contains_key(key) {
                continue;
            }
            if !provider
                .config
                .allowed_config_options
                .iter()
                .any(|allowed| allowed == key)
            {
                self.setup_failure(
                    &request.run_id,
                    &entry,
                    "coding_agent_config_not_allowed",
                    "ACP config override is not operator-allowed",
                );
                self.terminate_run_io(&mut child, &mut outbound);
                return;
            }
            if !self.apply_pre_prompt_config_option(
                &request.run_id,
                &entry,
                &mut child,
                &mut outbound,
                &rx,
                run_deadline,
                &session_id,
                &mut next_id,
                &mut advertised,
                key,
                value,
                false,
            ) {
                return;
            }
        }

        // Caller-allowed changes may have provider-side effects on another
        // option. Re-assert any forced value that drifted.
        for (key, value) in &self.forced_config {
            if config_override_is_valid(&advertised, key, value)
                && config_override_is_current(&advertised, key, value)
            {
                continue;
            }
            if !self.apply_pre_prompt_config_option(
                &request.run_id,
                &entry,
                &mut child,
                &mut outbound,
                &rx,
                run_deadline,
                &session_id,
                &mut next_id,
                &mut advertised,
                key,
                value,
                true,
            ) {
                return;
            }
        }

        // Final fail-closed check immediately before the prompt-dispatch path.
        if self.forced_config.iter().any(|(key, value)| {
            !config_override_is_valid(&advertised, key, value)
                || !config_override_is_current(&advertised, key, value)
        }) {
            self.setup_failure(
                &request.run_id,
                &entry,
                "coding_agent_forced_config_not_applied",
                "Runner-enforced ACP config was not active before prompt dispatch",
            );
            self.terminate_run_io(&mut child, &mut outbound);
            return;
        }
'''
text = text[:start] + "\n" + new_block + text[end:]
write(p, text)

# Add the new field to explicit AcpConfig test literals.
text = read(p)
for old, new in [
    (
'''        AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 1,
            agents: vec![AcpAgentConfig {''',
'''        AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 1,
            forced_config: BTreeMap::new(),
            agents: vec![AcpAgentConfig {'''
    ),
    (
'''        let cfg = AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 3,
            agents: vec![AcpAgentConfig {''',
'''        let cfg = AcpConfig {
            max_concurrent_runs: 1,
            permission_timeout_secs: 3,
            forced_config: BTreeMap::new(),
            agents: vec![AcpAgentConfig {'''
    ),
    (
'''        let cfg = AcpConfig {
            max_concurrent_runs: manager.max_concurrent_runs,
            permission_timeout_secs: 1,
            agents: manager''',
'''        let cfg = AcpConfig {
            max_concurrent_runs: manager.max_concurrent_runs,
            permission_timeout_secs: 1,
            forced_config: manager.forced_config.clone(),
            agents: manager'''
    ),
]:
    if old not in text:
        raise SystemExit(f"explicit AcpConfig literal marker missing: {old[:80]!r}")
    text = text.replace(old, new, 1)
write(p, text)

# Extend the existing fake ACP provider with generic model/effort cases.
text = read(p)
text = text.replace(
"config_values={'one':'a','two':'a','three':'a','four':'a'}",
"config_values={'one':'a','two':'a','three':'a','four':'a','mode':'agent','model':'default-model','reasoning_effort':'medium'}",
1,
)
old = """ elif method=='session/new':
  if scenario=='slow_configs':
   opts=[{'id':k,'name':k.title(),'type':'select','currentValue':config_values[k],'options':[{'value':'a','name':'A'},{'value':'b','name':'B'}]} for k in config_values]
  else:
   opts=[{'id':'mode','name':'Mode','type':'select','currentValue':'agent','options':[{'value':'agent','name':'Agent'},{'value':'read-only','name':'Read Only'}]}"""
new = """ elif method=='session/new':
  if scenario=='slow_configs':
   opts=[{'id':k,'name':k.title(),'type':'select','currentValue':config_values[k],'options':[{'value':'a','name':'A'},{'value':'b','name':'B'}]} for k in ('one','two','three','four')]
  elif scenario in ('forced_configs','forced_not_applied','forced_reset_by_caller'):
   opts=[
    {'id':'mode','name':'Mode','type':'select','currentValue':config_values['mode'],'options':[{'value':'agent','name':'Agent'},{'value':'read-only','name':'Read Only'}]},
    {'id':'model','name':'Model','type':'select','currentValue':config_values['model'],'options':[{'value':'default-model','name':'Default'},{'value':'policy-model','name':'Policy'}]},
    {'id':'reasoning_effort','name':'Reasoning Effort','type':'select','currentValue':config_values['reasoning_effort'],'options':[{'value':'medium','name':'Medium'},{'value':'high','name':'High'}]}
   ]
  else:
   opts=[{'id':'mode','name':'Mode','type':'select','currentValue':'agent','options':[{'value':'agent','name':'Agent'},{'value':'read-only','name':'Read Only'}]}"""
if old not in text:
    raise SystemExit("fake session/new marker missing")
text = text.replace(old, new, 1)

old = """ elif method=='session/set_config_option':
  if scenario=='slow_configs':
   time.sleep(0.6)
   k=m['params']['configId']; v=m['params']['value']; config_values[k]=v
   opts=[{'id':key,'name':key.title(),'type':'select','currentValue':config_values[key],'options':[{'value':'a','name':'A'},{'value':'b','name':'B'}]} for key in config_values]
  else:
   v=m['params']['value']; opts=[{'id':'mode','name':'Mode','type':'select','currentValue':v,'options':[{'value':'agent','name':'Agent'},{'value':'read-only','name':'Read Only'}]}"""
new = """ elif method=='session/set_config_option':
  if scenario=='slow_configs':
   time.sleep(0.6)
   k=m['params']['configId']; v=m['params']['value']; config_values[k]=v
   opts=[{'id':key,'name':key.title(),'type':'select','currentValue':config_values[key],'options':[{'value':'a','name':'A'},{'value':'b','name':'B'}]} for key in ('one','two','three','four')]
  elif scenario in ('forced_configs','forced_not_applied','forced_reset_by_caller'):
   k=m['params']['configId']; v=m['params']['value']
   if not (scenario=='forced_not_applied' and k=='model'):
    config_values[k]=v
   if scenario=='forced_reset_by_caller' and k=='mode':
    config_values['model']='default-model'; config_values['reasoning_effort']='medium'
   opts=[
    {'id':'mode','name':'Mode','type':'select','currentValue':config_values['mode'],'options':[{'value':'agent','name':'Agent'},{'value':'read-only','name':'Read Only'}]},
    {'id':'model','name':'Model','type':'select','currentValue':config_values['model'],'options':[{'value':'default-model','name':'Default'},{'value':'policy-model','name':'Policy'}]},
    {'id':'reasoning_effort','name':'Reasoning Effort','type':'select','currentValue':config_values['reasoning_effort'],'options':[{'value':'medium','name':'Medium'},{'value':'high','name':'High'}]}
   ]
  else:
   v=m['params']['value']; opts=[{'id':'mode','name':'Mode','type':'select','currentValue':v,'options':[{'value':'agent','name':'Agent'},{'value':'read-only','name':'Read Only'}]}"""
if old not in text:
    raise SystemExit("fake set_config marker missing")
text = text.replace(old, new, 1)
write(p, text)

# Add test helpers after received_config_ids.
text = read(p)
marker = '''    #[cfg(unix)]
    fn run_scenario('''
helpers = r'''    #[cfg(unix)]
    fn received_config_ids(log: &[Value]) -> Vec<String> {
        log.iter()
            .filter_map(|entry| {
                let recv = entry.get("recv")?;
                if recv.get("method").and_then(Value::as_str) != Some("session/set_config_option") {
                    return None;
                }
                recv.pointer("/params/configId")
                    .and_then(Value::as_str)
                    .map(str::to_string)
            })
            .collect()
    }

    #[cfg(unix)]
    fn force_policy(cfg: &mut AcpConfig) {
        cfg.forced_config = BTreeMap::from([
            (
                "model".to_string(),
                CodingAgentConfigValue::String("policy-model".to_string()),
            ),
            (
                "reasoning_effort".to_string(),
                CodingAgentConfigValue::String("high".to_string()),
            ),
        ]);
    }

    #[cfg(unix)]
    fn start_request_for_provider(
        manager: &CodingAgentManager,
        root: &Path,
        run: &str,
        provider_id: &str,
        config: BTreeMap<String, CodingAgentConfigValue>,
    ) -> CodingAgentRequest {
        let provider = manager
            .providers()
            .into_iter()
            .find(|provider| provider.provider_id == provider_id)
            .unwrap();
        CodingAgentRequest::Start(webcodex_core::coding_agent::CodingAgentStartRequest {
            run_id: run.to_string(),
            intent_fingerprint: format!("fingerprint-{provider_id}"),
            authority_fingerprint: "auth_test".to_string(),
            runtime_project_id: "agent:test:demo".to_string(),
            project_root: root.to_string_lossy().to_string(),
            provider_id: provider_id.to_string(),
            provider_instance_id: provider.provider_instance_id,
            instruction: "inspect".to_string(),
            config,
            timeout_secs: 10,
        })
    }

'''
if marker not in text:
    raise SystemExit("run_scenario marker missing")
text = text.replace(marker, helpers + marker, 1)
write(p, text)

# Insert focused runtime policy tests before the next setup-deadline test family.
text = read(p)
marker = '''    #[test]
    #[cfg(unix)]
    fn config_setup_cumulatively_consumes_total_run_deadline() {'''
tests = r'''    #[test]
    #[cfg(unix)]
    fn forced_config_is_applied_before_prompt() {
        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "forced_configs");
        let mut cfg = fake_config(exe, args);
        force_policy(&mut cfg);
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();
        let run = "wc_agent_run_forcedapply01";
        assert!(manager
            .handle(
                start_request(&manager, &root, run, BTreeMap::new()),
                &projects,
            )
            .error
            .is_none());
        let terminal = wait_for_snapshot(&manager, run, |snapshot| snapshot.state.terminal());
        assert_eq!(terminal.state, CodingAgentRunState::Completed);
        assert_eq!(
            received_config_ids(&wire_log(&temp)),
            vec!["model".to_string(), "reasoning_effort".to_string()]
        );
        assert_eq!(
            received_methods(&wire_log(&temp)),
            vec![
                "initialize",
                "session/new",
                "session/set_config_option",
                "session/set_config_option",
                "session/prompt",
            ]
        );
    }

    #[test]
    #[cfg(unix)]
    fn missing_forced_config_fails_without_prompt() {
        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "end");
        let mut cfg = fake_config(exe, args);
        cfg.forced_config.insert(
            "model".to_string(),
            CodingAgentConfigValue::String("policy-model".to_string()),
        );
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();
        let run = "wc_agent_run_forcedmissing01";
        assert!(manager
            .handle(
                start_request(&manager, &root, run, BTreeMap::new()),
                &projects,
            )
            .error
            .is_none());
        let terminal = wait_for_snapshot(&manager, run, |snapshot| snapshot.state.terminal());
        assert_eq!(terminal.state, CodingAgentRunState::Failed);
        assert_eq!(
            terminal
                .terminal
                .as_ref()
                .and_then(|terminal| terminal.error_code.as_deref()),
            Some("coding_agent_forced_config_not_advertised")
        );
        assert_eq!(
            received_methods(&wire_log(&temp))
                .iter()
                .filter(|method| method.as_str() == "session/prompt")
                .count(),
            0
        );
    }

    #[test]
    #[cfg(unix)]
    fn forced_config_must_be_reflected_by_provider() {
        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "forced_not_applied");
        let mut cfg = fake_config(exe, args);
        cfg.forced_config.insert(
            "model".to_string(),
            CodingAgentConfigValue::String("policy-model".to_string()),
        );
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();
        let run = "wc_agent_run_forcedreflect01";
        assert!(manager
            .handle(
                start_request(&manager, &root, run, BTreeMap::new()),
                &projects,
            )
            .error
            .is_none());
        let terminal = wait_for_snapshot(&manager, run, |snapshot| snapshot.state.terminal());
        assert_eq!(terminal.state, CodingAgentRunState::Failed);
        assert_eq!(
            terminal
                .terminal
                .as_ref()
                .and_then(|terminal| terminal.error_code.as_deref()),
            Some("coding_agent_forced_config_not_applied")
        );
        assert_eq!(
            received_methods(&wire_log(&temp))
                .iter()
                .filter(|method| method.as_str() == "session/prompt")
                .count(),
            0
        );
    }

    #[test]
    #[cfg(unix)]
    fn caller_may_repeat_but_not_override_forced_config() {
        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "forced_configs");
        let mut cfg = fake_config(exe, args);
        cfg.forced_config.insert(
            "model".to_string(),
            CodingAgentConfigValue::String("policy-model".to_string()),
        );
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();
        let same_run = "wc_agent_run_forcedsame0001";
        assert!(manager
            .handle(
                start_request(
                    &manager,
                    &root,
                    same_run,
                    BTreeMap::from([(
                        "model".to_string(),
                        CodingAgentConfigValue::String("policy-model".to_string()),
                    )]),
                ),
                &projects,
            )
            .error
            .is_none());
        assert_eq!(
            wait_for_snapshot(&manager, same_run, |snapshot| snapshot.state.terminal()).state,
            CodingAgentRunState::Completed
        );

        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "forced_configs");
        let mut cfg = fake_config(exe, args);
        cfg.forced_config.insert(
            "model".to_string(),
            CodingAgentConfigValue::String("policy-model".to_string()),
        );
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();
        let conflict_run = "wc_agent_run_forcedconflict01";
        assert!(manager
            .handle(
                start_request(
                    &manager,
                    &root,
                    conflict_run,
                    BTreeMap::from([(
                        "model".to_string(),
                        CodingAgentConfigValue::String("default-model".to_string()),
                    )]),
                ),
                &projects,
            )
            .error
            .is_none());
        let terminal =
            wait_for_snapshot(&manager, conflict_run, |snapshot| snapshot.state.terminal());
        assert_eq!(terminal.state, CodingAgentRunState::Failed);
        assert_eq!(
            terminal
                .terminal
                .as_ref()
                .and_then(|terminal| terminal.error_code.as_deref()),
            Some("coding_agent_forced_config_conflict")
        );
        assert!(received_config_ids(&wire_log(&temp)).is_empty());
        assert_eq!(
            received_methods(&wire_log(&temp))
                .iter()
                .filter(|method| method.as_str() == "session/prompt")
                .count(),
            0
        );
    }

    #[test]
    #[cfg(unix)]
    fn forced_config_is_reasserted_after_caller_side_effects() {
        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "forced_reset_by_caller");
        let mut cfg = fake_config(exe, args);
        force_policy(&mut cfg);
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();
        let run = "wc_agent_run_forcedreassert01";
        assert!(manager
            .handle(
                start_request(
                    &manager,
                    &root,
                    run,
                    BTreeMap::from([(
                        "mode".to_string(),
                        CodingAgentConfigValue::String("read-only".to_string()),
                    )]),
                ),
                &projects,
            )
            .error
            .is_none());
        assert_eq!(
            wait_for_snapshot(&manager, run, |snapshot| snapshot.state.terminal()).state,
            CodingAgentRunState::Completed
        );
        assert_eq!(
            received_config_ids(&wire_log(&temp)),
            vec![
                "model".to_string(),
                "reasoning_effort".to_string(),
                "mode".to_string(),
                "model".to_string(),
                "reasoning_effort".to_string(),
            ]
        );
    }

    #[test]
    #[cfg(unix)]
    fn global_forced_config_is_multi_provider_admission_policy() {
        let temp = TempDir::new().unwrap();
        let (exe, args) = fake_agent(&temp, "forced_configs");
        let mut cfg = fake_config(exe.clone(), args);
        cfg.forced_config.insert(
            "model".to_string(),
            CodingAgentConfigValue::String("policy-model".to_string()),
        );
        cfg.agents.push(AcpAgentConfig {
            id: "limited".to_string(),
            name: "Limited".to_string(),
            executable: exe,
            args: vec!["end".to_string()],
            env_from_env: BTreeMap::new(),
            allowed_config_options: vec!["mode".to_string()],
        });
        let projects = project_fixture(&temp);
        let root = temp.path().join("repo");
        let manager = CodingAgentManager::with_store(&cfg, temp.path().join("store")).unwrap();

        let supported_run = "wc_agent_run_forcedmultiok";
        assert!(manager
            .handle(
                start_request_for_provider(
                    &manager,
                    &root,
                    supported_run,
                    "codex",
                    BTreeMap::new(),
                ),
                &projects,
            )
            .error
            .is_none());
        assert_eq!(
            wait_for_snapshot(&manager, supported_run, |snapshot| snapshot.state.terminal()).state,
            CodingAgentRunState::Completed
        );
        let prompts_after_supported = received_methods(&wire_log(&temp))
            .iter()
            .filter(|method| method.as_str() == "session/prompt")
            .count();
        assert_eq!(prompts_after_supported, 1);

        let limited_run = "wc_agent_run_forcedmultifail";
        assert!(manager
            .handle(
                start_request_for_provider(
                    &manager,
                    &root,
                    limited_run,
                    "limited",
                    BTreeMap::new(),
                ),
                &projects,
            )
            .error
            .is_none());
        let terminal =
            wait_for_snapshot(&manager, limited_run, |snapshot| snapshot.state.terminal());
        assert_eq!(terminal.state, CodingAgentRunState::Failed);
        assert_eq!(
            terminal
                .terminal
                .as_ref()
                .and_then(|terminal| terminal.error_code.as_deref()),
            Some("coding_agent_forced_config_not_advertised")
        );
        assert_eq!(
            received_methods(&wire_log(&temp))
                .iter()
                .filter(|method| method.as_str() == "session/prompt")
                .count(),
            1,
            "unsupported provider must fail before prompt dispatch"
        );
    }

    #[test]
    #[cfg(unix)]
    fn config_setup_cumulatively_consumes_total_run_deadline() {'''
if marker not in text:
    raise SystemExit("runtime test insertion marker missing")
text = text.replace(marker, tests, 1)
write(p, text)

# ---------------------------------------------------------------------------
# Docs: explicit admission semantics and neutral example.
# ---------------------------------------------------------------------------
p = "docs/agent/acp-coding-agent-run.md"
text = read(p)
append = r'''

## Runner-global forced ACP configuration

Runner configuration may define a provider-neutral global forced policy:

    [acp.forced_config]
    model = "provider-model"
    feature_flag = true

The map is empty by default. Keys and values are provider-defined live ACP
configuration, not WebCodex model or effort enums.

This policy is admission policy, not best-effort configuration. For every new
ACP session the Runner validates every forced key/value against that session's
live session/new configOptions, applies it with session/set_config_option, and
requires the returned configuration state to reflect the requested value. A
globally forced key may not also appear in any provider's
allowed_config_options.

A caller may repeat the exact forced value. A conflicting caller value fails
closed before session/prompt. After caller-allowed options are applied, the
Runner re-checks and re-asserts forced values in case another setting changed
them as a provider-side effect, then performs one final forced-current check
immediately before the prompt-dispatch path.

The policy applies to every configured ACP provider on the Runner. If a provider
does not advertise a forced key/value, a Run targeting that provider fails
before prompt dispatch; the policy is never silently ignored for that provider.

The first version accepts stable ACP string/select and boolean values. Integer
forced values are rejected. The ACP section remains Runner
startup/restart-owned; forced-policy changes do not hot-reload.
'''
if "## Runner-global forced ACP configuration" not in text:
    text += append
write(p, text)

p = "deploy/webcodex-runner.toml.example"
text = read(p)
append = r'''

# Optional Runner-global ACP admission policy. Empty/omitted is the default.
# Values must be advertised by every provider session that is expected to run
# under this Runner. Unsupported providers fail closed before session/prompt.
# [acp.forced_config]
# model = "provider-model"
# feature_flag = true
'''
if "# Optional Runner-global ACP admission policy." not in text:
    text += append
write(p, text)

print("upstream global forced_config patch applied")
