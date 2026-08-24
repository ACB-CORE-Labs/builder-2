# DSH UI Interaction and Approval Spec

## Requirement
The user must remain entirely within the DeepSeek Harness (DSH) interactive UI to guide the agent, issue requests, and approve actions. They must not be forced to context-switch to a raw terminal to execute builder-II CLI commands to authorize routine workflow steps.

## The Problem
builder-II's governance strictly dictates: "Neither DSH nor Goose should mint or broaden the approval." Approvals must be cryptographic artifacts minted by the builder-II control plane. 

## The Solution: UI Trigger, Control Plane Execution
To satisfy both UX and Governance constraints:

1. **Interactive Chat and Generation**: The DSH UI functions normally as the primary interactive layer. User prompts entered in the DSH chat box are passed directly through the bridge to `goose acp`.
2. **Intercepting UI Approvals**: When `goose acp` hits a tool call requiring authorization, it pauses and bubbles up a permission request.
3. **Presenting the Gate**: The custom DSH plugin projects this as a standard "Allow / Deny" prompt within the DSH UI.
4. **Triggering the Mint**: When the user clicks "Allow" inside the DSH UI, the DSH framework does *not* natively authorize the action. Instead, the custom bridge intercepts this UI event and programmatically invokes the `builder-II HITL` API under the hood (e.g., executing the equivalent of the approval command).
5. **Resuming Execution**: The builder-II control plane mints the required artifact. The bridge then feeds this approval artifact reference back to Goose, which retries the tool call successfully.

This ensures the user never leaves the UI, while builder-II remains the exclusive minter of authority.
