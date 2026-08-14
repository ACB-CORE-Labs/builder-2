# ⚔️ The Execution Protocol

Follow these instructions to bypass the binary/UTF-8 corruption and feed this properly into the models:

1. **Repackage Locally**: Use a tool like Repomix or a quick bash script to dump the actual uncorrupted `.py`, `.rs`, and `.tcss` files into a clean text/Markdown format wrapped in XML tags (e.g., `<file path="builder_ii/validation/rust_validator.py">`).
2. **Load the DNA**: Paste the Universal System Instruction (The DNA) into your Gemini environment settings.
3. **Deploy the Strike**:
   - Feed **Gemini-3.1-Pro** the engine and Rust files along with **Brief Alpha**.
   - Feed **Gemini-3.5-Flash** the CLI, TUI, and config files along with **Brief Beta**.
