
use serde_json::Value;
use std::env;
use std::io::{self, Read};

mod validation;


fn main() {
    let args: Vec<String> = env::args().collect();
    if args.contains(&"--help".to_string()) || args.contains(&"-h".to_string()) {
        println!("builder-validator-rs — Rust-backed validation accelerator");
        println!("Usage: builder_ii_validation_rs --kind <kind> [JSON on stdin]");
        return;
    }

    let mut kind_arg = None;
    for i in 0..args.len() {
        if args[i] == "--kind" && i + 1 < args.len() {
            kind_arg = Some(args[i + 1].clone());
        }
    }

    let kind = match kind_arg {
        Some(k) => k,
        None => {
            eprintln!("Error: --kind is required");
            std::process::exit(1);
        }
    };

    let mut input = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut input) {
        println!("{}", serde_json::json!({
            "valid": false,
            "errors": [format!("Failed to read stdin: {}", e)]
        }));
        return;
    }

    let json_data: Value = match serde_json::from_str(&input) {
        Ok(v) => v,
        Err(e) => {
            println!("{}", serde_json::json!({
                "valid": false,
                "errors": [format!("invalid JSON: {}", e)]
            }));
            return;
        }
    };

    let errors = validation::validate_artifact_core(&kind, &json_data);
    let valid = errors.is_empty();
    
    println!("{}", serde_json::json!({
        "valid": valid,
        "errors": errors
    }));
}

fn validate_artifact(kind: &str, data: &Value) -> Vec<String> {
    let mut errors = Vec::new();

    if !data.is_object() {
        errors.push(format!("{} must be a JSON object", match kind {
            "builder_ii.goose_session_manifest" => "goose session manifest",
            "builder_ii.goose_readonly_runtime_audit" => "Goose read-only audit",
            _ => "artifact"
        }));
        return errors;
    }

    // Common checks
    if data.get("kind").and_then(|v| v.as_str()) != Some(kind) {
        errors.push(format!("kind must be {}", kind));
    }

    match kind {
        "builder_ii.goose_session_manifest" => {
            validate_goose_session_manifest(data, &mut errors);
        }
        "builder_ii.goose_readonly_runtime_audit" => {
            validate_readonly_runtime_audit(data, &mut errors);
        }
        _ => {
            // Fallback: not fully implemented in Rust yet, or unsupported
            // We just do basic kind verification in Rust and let Python handle the rest if parity is verified
        }
    }

    errors
}

fn validate_goose_session_manifest(data: &Value, errors: &mut Vec<String>) {
    if data.get("schema_version").and_then(|v| v.as_i64()) != Some(1) {
        errors.push("schema_version must be 1".to_string());
    }
    if data.get("current_runtime_state").and_then(|v| v.as_str()) != Some("DISABLED") {
        errors.push("current_runtime_state must be DISABLED".to_string());
    }
    if data.get("manifest_starts_goose").and_then(|v| v.as_bool()) != Some(false) {
        errors.push("manifest_starts_goose must be false".to_string());
    }

    if let Some(target) = data.get("target") {
        if !target.is_object() {
            errors.push("target must be an object".to_string());
        } else {
            let name = target.get("name").and_then(|v| v.as_str()).unwrap_or("");
            if name != "generic" && name != "builder" && name != "core" {
                errors.push("target.name must be one of: generic, builder, core".to_string());
            }
            if target.get("repo").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
                errors.push("target.repo is required".to_string());
            }
        }
    } else {
        errors.push("target is required".to_string());
    }

    if let Some(agent) = data.get("agent_profile") {
        if !agent.is_object() {
            errors.push("agent_profile must be an object".to_string());
        } else if agent.get("name").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
            errors.push("agent_profile.name is required".to_string());
        }
    } else {
        errors.push("agent_profile is required".to_string());
    }

    let mode = data.get("requested_runtime_mode").and_then(|v| v.as_str()).unwrap_or("");
    if mode != "disabled" && mode != "read_only" {
        errors.push("requested_runtime_mode must be disabled or read_only".to_string());
    }

    if let Some(denied) = data.get("denied_actions").and_then(|v| v.as_array()) {
        let denied_strs: Vec<&str> = denied.iter().filter_map(|v| v.as_str()).collect();
        for action in &["start_goose_runtime", "read_repository_files_as_runtime", "execute_commands", "execute_shell", "write_source_files"] {
            if !denied_strs.contains(action) {
                errors.push(format!("denied_actions must include {}", action));
            }
        }
    } else {
        errors.push("denied_actions must be a list".to_string());
    }

    if let Some(gov) = data.get("governance") {
        if !gov.is_object() {
            errors.push("governance must be an object".to_string());
        } else {
            for key in &["runtime_execution", "goose_runtime_start", "command_execution", "source_writes"] {
                if gov.get(*key).and_then(|v| v.as_str()) != Some("DISABLED") {
                    errors.push(format!("governance.{} must be DISABLED", key));
                }
            }
            if gov.get("artifact_is_authority").and_then(|v| v.as_bool()) != Some(false) {
                errors.push("governance.artifact_is_authority must be false".to_string());
            }
        }
    } else {
        errors.push("governance is required".to_string());
    }
}

fn validate_readonly_runtime_audit(data: &Value, errors: &mut Vec<String>) {
    if data.get("schema_version").and_then(|v| v.as_i64()) != Some(1) {
        errors.push("schema_version must be 1".to_string());
    }
    if data.get("runtime_mode").and_then(|v| v.as_str()) != Some("read_only") {
        errors.push("runtime_mode must be read_only".to_string());
    }
    if data.get("capability_state").and_then(|v| v.as_str()) != Some("read_only_runtime_candidate") {
        errors.push("capability_state must be read_only_runtime_candidate".to_string());
    }
    if data.get("current_runtime_state").and_then(|v| v.as_str()) != Some("DISABLED") {
        errors.push("current_runtime_state must be DISABLED".to_string());
    }
    if data.get("runtime_started").and_then(|v| v.as_bool()) != Some(false) {
        errors.push("runtime_started must be false".to_string());
    }
    if data.get("goose_process_started").and_then(|v| v.as_bool()) != Some(false) {
        errors.push("goose_process_started must be false".to_string());
    }
    if data.get("manifest_requested_runtime_mode").and_then(|v| v.as_str()) != Some("read_only") {
        errors.push("manifest_requested_runtime_mode must be read_only".to_string());
    }
    if data.get("manifest_path").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
        errors.push("manifest_path is required".to_string());
    }

    if let Some(target) = data.get("target") {
        if !target.is_object() {
            errors.push("target must be an object".to_string());
        } else if target.get("name").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
            errors.push("target.name is required".to_string());
        }
    } else {
        errors.push("target is required".to_string());
    }

    if let Some(agent) = data.get("agent_profile") {
        if !agent.is_object() {
            errors.push("agent_profile must be an object".to_string());
        } else if agent.get("name").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
            errors.push("agent_profile.name is required".to_string());
        }
    } else {
        errors.push("agent_profile is required".to_string());
    }

    let lists = [
        "actions_performed", "allowed_actions", "denied_actions", "files_read",
        "repository_files_read", "target_artifacts_read", "commands_proposed",
        "commands_executed", "shell_commands_executed", "source_writes_proposed",
        "source_writes_applied", "patches_applied", "model_calls",
        "denied_action_attempts", "approval_events", "verification_output_refs",
        "rollback_refs"
    ];
    for list in &lists {
        if !data.get(*list).map_or(false, |v| v.is_array()) {
            errors.push(format!("{} must be a list", list));
        }
    }

    if let Some(denied) = data.get("denied_actions").and_then(|v| v.as_array()) {
        let denied_strs: Vec<&str> = denied.iter().filter_map(|v| v.as_str()).collect();
        for action in &["start_goose_process", "start_goose_runtime", "read_repository_files", "inspect_git_status"] {
            if !denied_strs.contains(action) {
                errors.push(format!("denied_actions must include {}", action));
            }
        }
    }

    if data.get("repository_files_read").and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty()) {
        errors.push("repository_files_read must be empty".to_string());
    }
    if data.get("target_artifacts_read").and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty()) {
        errors.push("target_artifacts_read must be empty".to_string());
    }
    if data.get("git_status_inspected").and_then(|v| v.as_bool()) != Some(false) {
        errors.push("git_status_inspected must be false".to_string());
    }
    if data.get("commands_executed").and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty()) {
        errors.push("commands_executed must be empty".to_string());
    }
    if data.get("shell_commands_executed").and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty()) {
        errors.push("shell_commands_executed must be empty".to_string());
    }
    if data.get("source_writes_applied").and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty()) {
        errors.push("source_writes_applied must be empty".to_string());
    }
    if data.get("patches_applied").and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty()) {
        errors.push("patches_applied must be empty".to_string());
    }
    if data.get("model_calls").and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty()) {
        errors.push("model_calls must be empty".to_string());
    }
    if data.get("deepagents_constructed").and_then(|v| v.as_bool()) != Some(false) {
        errors.push("deepagents_constructed must be false".to_string());
    }

    if let Some(gov) = data.get("governance") {
        if !gov.is_object() {
            errors.push("governance must be an object".to_string());
        } else {
            if gov.get("capability_state").and_then(|v| v.as_str()) != Some("read_only_runtime_candidate") {
                errors.push("governance.capability_state must be read_only_runtime_candidate".to_string());
            }
            if gov.get("repository_file_reads").and_then(|v| v.as_str()) != Some("DISABLED_IN_THIS_CANDIDATE_ARTIFACT") {
                errors.push("governance.repository_file_reads must be DISABLED_IN_THIS_CANDIDATE_ARTIFACT".to_string());
            }
            if gov.get("target_artifact_reads").and_then(|v| v.as_str()) != Some("DISABLED_IN_THIS_CANDIDATE_ARTIFACT") {
                errors.push("governance.target_artifact_reads must be DISABLED_IN_THIS_CANDIDATE_ARTIFACT".to_string());
            }
            if gov.get("artifact_is_authority").and_then(|v| v.as_bool()) != Some(false) {
                errors.push("governance.artifact_is_authority must be false".to_string());
            }
        }
    } else {
        errors.push("governance is required".to_string());
    }
}
