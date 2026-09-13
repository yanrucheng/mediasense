> 本轮用户已明确授权并接受本包信息/失败边界；对应语义已采用到 `docs/spec/contract/`。此处保留 change delta，当前合约仍是唯一交换值权威。

## ADDED Requirements

### Requirement: Selected local sensitivity recipes have explicit prerequisites
The release SHALL declare compatible dependencies, local asset identities and effective recipes for Freepik/nsfw_image_detector at revision 15b85477e4fd2000db76ae9aae0f89a72f95e2e3 and NudeNet 640m at weight SHA-256 04fe3d77980780c1f8297dc6d7f942fd5b3abe6942a188f742a85241e4f634eb. It SHALL preserve the selected official Freepik preprocessing and native 640 processing and SHALL verify actual local execution requirements. Production code and configuration MUST NOT depend on Downloads, evaluation scripts or automatic model acquisition.

#### Scenario: Freepik dependencies are prepared for the release
- **WHEN** the selected package is built for the supported MPS FP32 profile
- **THEN** the dependency plan includes the required compatible Timm/Transformers path and its actual preprocessing, not merely a replacement model ID in the old classifier

#### Scenario: NudeNet 640 assets are selected
- **WHEN** the configured file is resolved for execution
- **THEN** its pinned content identity and retained mirror/source limitation are verified and no packaged 320 weight or differently named 640 file is silently substituted

### Requirement: Sensitivity diagnostics separate configuration and execution readiness
Existing configuration and diagnostic surfaces SHALL distinguish each model's selected or disabled state, expected profile, local asset/dependency prerequisites and verified execution facts. Configuration parsing and retained-result reads SHALL not require inference. Unknown keys, unsupported profiles and conflicting settings SHALL be actionable configuration errors for new work rather than silent omissions. Legacy explicit configuration SHALL not be reinterpreted as the new model choice.

#### Scenario: A disabled optional model has no installed dependencies
- **WHEN** the user reads configuration or a historical Result
- **THEN** the missing optional inference installation does not prevent that read and diagnostics do not claim new execution occurred

#### Scenario: The old four-key sensitivity table is supplied
- **WHEN** it cannot express the new independently selected profiles
- **THEN** new execution reports the required explicit configuration migration without silently replacing Falconsai/320 or preventing independent historical reads

#### Scenario: Actual backend is unverified
- **WHEN** only files and dependency metadata were checked
- **THEN** diagnostics report those prerequisite facts without claiming the model has executed successfully on the requested device

### Requirement: Sensitivity release acceptance covers the installed consumer path
A conforming release SHALL demonstrate the selected dependency and asset combination through its actual CLI/MCP composition, PreCheck execution, immutable publication and public Read consumption. It SHALL separately prove per-model disablement, missing-prerequisite handling, valid reuse and historical reads without model packages. The canonical installation runbook and packaged snapshot SHALL be synchronized. Source tests or tool discovery alone SHALL NOT certify installed sensitivity delivery.

#### Scenario: Both selected profiles execute through an isolated installed Host
- **WHEN** a bounded approved image/frame fixture is processed
- **THEN** Read delivers both model outputs with exact input bindings, probabilities/events and every retained region instance, while source bytes and external-effect boundaries are preserved

#### Scenario: A successor Run reuses valid work
- **WHEN** inputs and effective profiles are unchanged
- **THEN** no new corresponding model attempt is recorded and the published successor Result preserves the original observation provenance

#### Scenario: Release artifacts are prepared before daily installation
- **WHEN** source, wheel and isolated execution checks pass
- **THEN** the evidence identifies that verified scope and does not claim the daily Host or user/Dataset configuration has changed without the corresponding authorization and actual verification
