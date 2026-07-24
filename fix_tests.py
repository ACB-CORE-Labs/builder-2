import os
import re

tests_dir = "tests"

pattern_plan = re.compile(r'finalize_verification_execution_plan\(')
pattern_approval = re.compile(r'finalize_verification_execution_approval\(')
pattern_receipt = re.compile(r'finalize_verification_execution_receipt\(')

replacement = r'\g<0>target_head_sha="0000000000000000000000000000000000000000", tree_clean=True, '

for root, _, files in os.walk(tests_dir):
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            with open(filepath, "r") as file:
                content = file.read()
            
            new_content = pattern_plan.sub(replacement, content)
            new_content = pattern_approval.sub(replacement, new_content)
            new_content = pattern_receipt.sub(replacement, new_content)
            
            if new_content != content:
                with open(filepath, "w") as file:
                    file.write(new_content)
                print(f"Updated {filepath}")
