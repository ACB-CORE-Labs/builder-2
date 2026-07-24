import os
import re

tests_dir = "tests"

# find all calls
pattern_approval = re.compile(r'finalize_verification_execution_approval\((.*?)\)', re.DOTALL)

for root, _, files in os.walk(tests_dir):
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            with open(filepath, "r") as file:
                content = file.read()
            
            def repl(m):
                args = m.group(1)
                if 'expires_at=' not in args:
                    return f'finalize_verification_execution_approval(expires_at="2030-01-01T00:00:00Z", {args})'
                return m.group(0)

            new_content = pattern_approval.sub(repl, content)
            
            if new_content != content:
                with open(filepath, "w") as file:
                    file.write(new_content)
                print(f"Updated {filepath}")
