import os
import re

tests_dir = "tests"

revert_pattern_approval = re.compile(r'finalize_verification_execution_approval\(target_head_sha="0000000000000000000000000000000000000000", tree_clean=True, ')
revert_pattern_receipt = re.compile(r'finalize_verification_execution_receipt\(target_head_sha="0000000000000000000000000000000000000000", tree_clean=True, ')

replacement_approval = r'finalize_verification_execution_approval('
replacement_receipt = r'finalize_verification_execution_receipt('

for root, _, files in os.walk(tests_dir):
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            with open(filepath, "r") as file:
                content = file.read()
            
            new_content = revert_pattern_approval.sub(replacement_approval, content)
            new_content = revert_pattern_receipt.sub(replacement_receipt, new_content)
            
            if new_content != content:
                with open(filepath, "w") as file:
                    file.write(new_content)
                print(f"Reverted {filepath}")
