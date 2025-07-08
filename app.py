import pandas as pd
import streamlit as st
import json
import os
import random
import time

# ========== 配置 ==========
OPTION_KEYS = list("ABCDEF")  # 只支持A~F，如更多请自行扩展
QUESTION_PATH = "data/question_bank_zh.csv"
CORRECT_BOOK_PATH = "data/correct_book.json"
WRONG_BOOK_PATH = "data/wrong_book.json"
SCORE_BOOK_PATH = "data/score_book.json"
STARRED_PATH = "data/starred.json"

USECOLS = ["id", "question", "answer"] + OPTION_KEYS + ["question_zh"] + [f"{k}_zh" for k in OPTION_KEYS]

# ========== 工具函数 ==========
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_questions():
    if not os.path.exists(QUESTION_PATH):
        st.error(f"未找到题库文件：{QUESTION_PATH}")
        st.stop()
    return pd.read_csv(QUESTION_PATH, usecols=USECOLS, dtype=str)

# ========== 题目中英切换 ==========
def get_display_question(row, zh=False):
    q_show = {}
    q_show['id'] = row['id']
    q_show['question'] = row['question_zh'] if zh and pd.notna(row.get('question_zh')) else row['question']
    q_show['answer'] = row['answer']
    for k in OPTION_KEYS:
        q_show[k] = row.get(f"{k}_zh") if zh and pd.notna(row.get(f"{k}_zh")) else row.get(k)
    return q_show

# ========== 数据持久化 ==========
correct_book = load_json(CORRECT_BOOK_PATH)
wrong_book = load_json(WRONG_BOOK_PATH)
score_book = load_json(SCORE_BOOK_PATH)
starred = load_json(STARRED_PATH)

# ========== 智能选题（优先未做、低分、错题） ==========
def pick_questions_with_score(pool, num):
    def get_score(q):
        return score_book.get(str(q['id']), 0)
    def never_done(q):
        qid = str(q['id'])
        return 1 if correct_book.get(qid, 0) == 0 and wrong_book.get(qid, 0) == 0 else 0
    pool_sorted = sorted(
        pool,
        key=lambda q: (
            get_score(q),
            -never_done(q),
            random.random()
        )
    )
    return pool_sorted[:num]

# ========== 主界面 ==========
def quiz_app():
    st.title("📝 我的刷题系统")

    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False

    if not st.session_state.quiz_started:
        col1, col2 = st.columns(2)
        with col1:
            num_questions = st.number_input("选择题目数量", 5, len(questions_df), 10, 1)
        with col2:
            scope = st.selectbox("选择题库范围", ["全部", "标记和错题","仅标记", "仅错题"])
        if st.button("🚩 开始答题"):
            if scope == "全部":
                pool = questions_df.to_dict('records')
            elif scope == "仅错题":
                pool = questions_df[questions_df['id'].astype(str).isin(wrong_book.keys())].to_dict('records')
            elif scope == "仅标记":
                pool = questions_df[questions_df['id'].astype(str).isin(starred.keys())].to_dict('records')
            else:
                all_ids = set(wrong_book.keys()) | set(starred.keys())
                pool = questions_df[questions_df['id'].astype(str).isin(all_ids)].to_dict('records')
            sample_num = min(num_questions, len(pool))
            if sample_num == 0:
                st.warning("题库范围内暂无可选题目，请检查错题本/标记。")
                return
            selected = pick_questions_with_score(pool, sample_num)
            st.session_state.selected_questions = selected
            st.session_state.answers = {}
            st.session_state.current_qid = 0
            st.session_state.start_time = time.time()
            st.session_state.elapsed_time = 0
            st.session_state.paused = False
            st.session_state.quiz_started = True
            st.session_state.from_stat = False
            st.rerun()
        if st.button("📊 查看统计"):
            st.session_state.view_stat = True
            st.rerun()
    else:
        show_question_page()

# ========== 题目页面 ==========
def show_question_page():
    if 'paused' not in st.session_state:
        st.session_state.paused = False
    if 'elapsed_time' not in st.session_state:
        st.session_state.elapsed_time = 0
    if 'start_time' not in st.session_state:
        st.session_state.start_time = time.time()
    if 'current_qid' not in st.session_state:
        st.session_state.current_qid = 0

    timer_container = st.empty()
    qid = st.session_state.current_qid
    raw_question = st.session_state.selected_questions[qid]

    # ====== 中英切换按钮 ======
    if 'translate' not in st.session_state:
        st.session_state.translate = False
    if st.button("🌐 翻译为中文" if not st.session_state.translate else "🌐 查看原文"):
        st.session_state.translate = not st.session_state.translate
        st.rerun()

    is_zh = st.session_state.translate
    question = get_display_question(raw_question, zh=is_zh)

    if not st.session_state.paused:
        st.session_state.elapsed_time += time.time() - st.session_state.start_time
        st.session_state.start_time = time.time()
    mins, secs = divmod(int(st.session_state.elapsed_time), 60)
    timer_container.info(f"⏱️ 用时：{mins:02d}:{secs:02d}")

    # ====== 统计跳转的题目特殊显示 ======
    if st.session_state.get("from_stat", False):
        st.markdown(f"### 题号 {question['id']}")
        st.markdown(question['question'])

        ans_val = question.get('answer', '')
        correct_ans = set(str(ans_val)) if ans_val else set()
        option_keys = [k for k in OPTION_KEYS if k in question and pd.notna(question[k])]
        for k in option_keys:
            option_text = f"{k}. {question[k]}"
            if k in correct_ans:
                st.markdown(f"<span style='color:green;'>✔️ {option_text}（正确答案）</span>", unsafe_allow_html=True)
            else:
                st.markdown(option_text)

        # 按钮区
        if st.button("🔙 返回统计", key=f"back_stat_{question['id']}"):
            st.session_state.quiz_started = False
            st.session_state.view_stat = True
            st.session_state.from_stat = False
            st.rerun()

        cols = st.columns(3)
        if cols[0].button("⏮️ 上一题", key=f"prev_{qid}") and qid > 0:
            st.session_state.current_qid -= 1
            st.rerun()
        if cols[1].button("⏭️ 下一题", key=f"next_{qid}") and qid < len(st.session_state.selected_questions) - 1:
            st.session_state.current_qid += 1
            st.rerun()
        if cols[2].button("📋 答题卡", key=f"card_{qid}"):
            st.session_state.show_card = True

        # ⭐ 收藏
        is_starred = str(question['id']) in starred
        if st.checkbox("⭐ 收藏本题", value=is_starred, key=f"star_{qid}"):
            starred[str(question['id'])] = True
        else:
            starred.pop(str(question['id']), None)
        save_json(STARRED_PATH, starred)
        return

    # ====== 正常刷题流程 ======
    st.markdown(f"### 题目 {qid + 1}/{len(st.session_state.selected_questions)}")
    st.markdown(question['question'])

    option_keys = [k for k in OPTION_KEYS if k in question and pd.notna(question[k])]
    correct_set = set(str(question['answer'])) if question['answer'] else set()
    is_multi = len(correct_set) > 1

    if qid not in st.session_state.answers:
        st.session_state.answers[qid] = set()

    if is_multi:
        for opt in option_keys:
            label = f"{opt}. {question[opt]}"
            checkbox_key = f"{qid}_{opt}"
            checked = opt in st.session_state.answers[qid]
            new_value = st.checkbox(label, value=checked, key=checkbox_key)
            if new_value:
                st.session_state.answers[qid].add(opt)
            else:
                st.session_state.answers[qid].discard(opt)
    else:
        current_ans = list(st.session_state.answers[qid])
        selected = st.radio(
            "请选择一个选项：",
            options=[""] + option_keys,
            format_func=lambda x: f"{x}. {question[x]}" if x else "（未选择）",
            index=([""] + option_keys).index(current_ans[0]) if current_ans else 0,
            key=f"radio_{qid}"
        )
        if selected:
            st.session_state.answers[qid] = {selected}

    # 按钮栏
    cols = st.columns(3)
    if cols[0].button("⏮️ 上一题") and qid > 0:
        st.session_state.current_qid -= 1
        st.rerun()
    if cols[1].button("⏭️ 下一题") and qid < len(st.session_state.selected_questions) - 1:
        st.session_state.current_qid += 1
        st.rerun()
    if cols[2].button("📋 答题卡"):
        st.session_state.show_card = True

    if st.button("⏸️ 暂停" if not st.session_state.paused else "▶️ 继续"):
        st.session_state.paused = not st.session_state.paused
        st.session_state.start_time = time.time()
        st.rerun()

    # ==== 提交弹窗 ====
    if 'show_submit_options' not in st.session_state:
        st.session_state.show_submit_options = False

    if st.button("✅ 提交"):
        st.session_state.show_submit_options = True

    if st.session_state.show_submit_options:
        submit_mode = st.radio(
            "请选择提交模式",
            ["全部提交（未答视为错误）", "仅提交已回答题目"],
            key="submit_mode_radio"
        )
        cols = st.columns(2)
        if cols[0].button("确定提交"):
            st.session_state.quiz_sub_mode = submit_mode
            st.session_state.quiz_started = False
            st.session_state.submitted = True
            st.session_state.show_submit_options = False
            st.rerun()
        if cols[1].button("取消"):
            st.session_state.show_submit_options = False
            st.rerun()

    # ⭐ 收藏
    is_starred = str(question['id']) in starred
    if st.checkbox("⭐ 收藏本题", value=is_starred):
        starred[str(question['id'])] = True
    else:
        starred.pop(str(question['id']), None)
    save_json(STARRED_PATH, starred)

    # 答题卡
    if 'show_card' in st.session_state and st.session_state.show_card:
        st.sidebar.title("📋 答题卡")
        for i in range(len(st.session_state.selected_questions)):
            ans = st.session_state.answers.get(i, set())
            if not ans or ans == {""}:
                label = f"题目 {i+1} - ❌"
            else:
                label = f"题目 {i+1} - ✅"
            if st.sidebar.button(label, key=f'card_{i}'):
                st.session_state.current_qid = i
                st.session_state.show_card = False
                st.rerun()

# ========== 结果页面 ==========
def result_page():
    st.title("📊 答题结果")
    submit_mode = st.session_state.get("quiz_sub_mode", "全部提交（未答视为错误）")
    st.write("提交模式：", submit_mode)
    correct = 0
    total = 0
    if 'scored' not in st.session_state:
        st.session_state.scored = False
    if not st.session_state.scored:
        for i, q in enumerate(st.session_state.selected_questions):
            user_ans = st.session_state.answers.get(i, set())
            correct_ans = set(str(q['answer']))
            qid = str(q['id'])
            if submit_mode == "仅提交已回答题目":
                if not user_ans or user_ans == {""}:
                    continue
            total += 1
            if user_ans == correct_ans:
                correct += 1
                correct_book[qid] = correct_book.get(qid, 0) + 1
                score_book[qid] = score_book.get(qid, 0) + 1
            else:
                wrong_book[qid] = wrong_book.get(qid, 0) + 1
                score_book[qid] = score_book.get(qid, 0) - 1
        save_json(CORRECT_BOOK_PATH, correct_book)
        save_json(WRONG_BOOK_PATH, wrong_book)
        save_json(SCORE_BOOK_PATH, score_book)
        st.session_state.scored = True
    else:
        for i, q in enumerate(st.session_state.selected_questions):
            user_ans = st.session_state.answers.get(i, set())
            correct_ans = set(str(q['answer']))
            if submit_mode == "仅提交已回答题目":
                if not user_ans or user_ans == {""}:
                    continue
            total += 1
            if user_ans == correct_ans:
                correct += 1
    st.success(f"🎉 正确数 {correct}/{total}")
    st.markdown("---")
    st.markdown("### 错题回顾")
    for i, q in enumerate(st.session_state.selected_questions):
        user_ans = st.session_state.answers.get(i, set())
        correct_ans = set(str(q['answer']))
        if submit_mode == "仅提交已回答题目" and (not user_ans or user_ans == {""}):
            continue
        if user_ans != correct_ans:
            expander = st.expander(f"❌ 第{i+1}题 (你的答案 {','.join(user_ans) if user_ans else '未答'})")
            q_disp = get_display_question(q, zh=st.session_state.get("translate", False))
            expander.markdown(q_disp['question'])
            option_keys = [k for k in OPTION_KEYS if k in q_disp and pd.notna(q_disp[k])]
            for k in option_keys:
                option_text = f"{k}. {q_disp[k]}"
                is_user = k in user_ans
                is_correct = k in correct_ans
                if is_user and is_correct:
                    expander.markdown(f"<span style='color:green;'>✔️ {option_text}（你的选择，正确）</span>", unsafe_allow_html=True)
                elif is_user:
                    expander.markdown(f"<span style='color:red;'>❌ {option_text}（你的选择）</span>", unsafe_allow_html=True)
                elif is_correct:
                    expander.markdown(f"<span style='color:green;'>✔️ {option_text}（正确答案）</span>", unsafe_allow_html=True)
                else:
                    expander.markdown(option_text)
            expander.info(f"✅ 正确答案：{q['answer']}")
    save_json(CORRECT_BOOK_PATH, correct_book)
    save_json(WRONG_BOOK_PATH, wrong_book)
    save_json(SCORE_BOOK_PATH, score_book)
    if st.button("🔄 再来一次"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ========== 统计页面 ==========
def stat_page():
    st.title("📊 答题统计")
    if st.button("返回主页"):
        st.session_state.view_stat = False
        st.rerun()
    if 'stat_filter' not in st.session_state:
        st.session_state.stat_filter = '全部'
    filters = ['全部', '仅错题', '仅标记', '错题+标记']
    stat_filter = st.radio(
        "题目范围", filters,
        index=filters.index(st.session_state.stat_filter),
        horizontal=True,
        key="stat_radio"
    )
    st.session_state.stat_filter = stat_filter
    wrong_ids = set(wrong_book.keys())
    star_ids = set(starred.keys())
    if stat_filter == '仅错题':
        filtered_df = questions_df[questions_df['id'].astype(str).isin(wrong_ids)]
    elif stat_filter == '仅标记':
        filtered_df = questions_df[questions_df['id'].astype(str).isin(star_ids)]
    elif stat_filter == '错题+标记':
        combined_ids = wrong_ids | star_ids
        filtered_df = questions_df[questions_df['id'].astype(str).isin(combined_ids)]
    else:
        filtered_df = questions_df
    for idx, row in enumerate(filtered_df.itertuples()):
        qid = str(row.id)
        ticks = "√" * correct_book.get(qid, 0) + "×" * wrong_book.get(qid, 0)
        star = "⭐" if qid in starred else ""
        score = score_book.get(qid, 0)
        label = f"{star}{qid}:{ticks or '-'} (分数{score})"
        if st.button(label, key=f"stat_{stat_filter}_{qid}"):
            st.session_state.selected_questions = filtered_df.to_dict('records')
            st.session_state.current_qid = idx
            st.session_state.answers = {}
            st.session_state.quiz_started = True
            st.session_state.from_stat = True
            st.session_state.view_stat = False
            st.session_state.stat_filter = stat_filter
            st.rerun()

# ========== 页面调度 ==========
questions_df = load_questions()
if st.session_state.get("submitted", False):
    result_page()
elif st.session_state.get("view_stat", False):
    stat_page()
else:
    quiz_app()
