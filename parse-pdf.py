import re
import pandas as pd

with open("source/awssoatxt.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 主正则：确保包含所有段落
pattern = re.compile(
    r"Question\s+#(?P<qid>\d+).*?\n+(?P<question>.*?)(?=(?:\n[A-Z]\. ))(?P<options>.*?)\n+Correct Answer:\s*(?P<answer>[A-Z,]+)",
    re.DOTALL
)

# 新：强力匹配所有 A. ... B. ...（支持多行）
option_pattern = re.compile(r"([A-Z])\. (.*?)(?=(?: [A-Z]\. )|$)", re.DOTALL)

questions = []

for match in pattern.finditer(text):
    qid = int(match.group("qid"))
    question = match.group("question").strip().replace("\n", " ")
    options_block = match.group("options").strip().replace("\n", " ")
    answer = match.group("answer").strip()

    # 抽取 A~Z
    option_dict = {}
    for opt_match in option_pattern.finditer(options_block):
        label, content = opt_match.groups()
        option_dict[label] = content.strip()

    row = {
        "id": qid,
        "question": question,
        "answer": answer,
    }
    row.update(option_dict)
    questions.append(row)

df = pd.DataFrame(questions).sort_values(by="id")
df.to_csv("data/question_bank_parsed.csv", index=False, encoding="utf-8-sig")
print(f"✅ 强化版解析完成，提取题目数：{len(df)}，已写入 CSV")
