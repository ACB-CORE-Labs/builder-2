import os

test_dir = "tests"
for root, dirs, files in os.walk(test_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()
            
            new_content = content.replace('"0000000000000000000000000000000000000000"', '"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"')
            new_content = new_content.replace('("a" * 40)', '"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"')
            
            if content != new_content:
                with open(path, "w") as f:
                    f.write(new_content)
                print(f"Updated {path}")
