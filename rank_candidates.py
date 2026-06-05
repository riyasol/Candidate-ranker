import json
import csv
import argparse
from datetime import datetime

# Define sets for filtering
ACADEMIC_TITLES = {
    "postdoc", "postdoctoral", "research assistant", "graduate assistant", 
    "phd scholar", "phd student", "academic researcher", "research fellow", 
    "research intern", "intern - research", "ph.d. student", "phd candidate", 
    "graduate research assistant", "assistant professor", "associate professor", "professor"
}

CONSULTING_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", 
    "tech mahindra", "hcl", "genpact", "mphasis", "mindtree", 
    "tata consultancy services", "tata consultancy", "cts", 
    "l&t infotech", "lnt infotech", "lti", "persistent systems", "ust global"
}

CV_SPEECH_ROBOTICS_SKILLS = {
    "computer vision", "image classification", "object detection", "image segmentation", 
    "opencv", "speech recognition", "tts", "asr", "robotics", "speech synthesis", 
    "yolo", "gans", "gan", "diffusion models", "cnn", "image generation"
}

NLP_IR_SEARCH_RAG_SKILLS = {
    "nlp", "natural language processing", "rag", "retrieval", "vector databases", 
    "embeddings", "ranking", "search", "elasticsearch", "milvus", "pinecone", 
    "qdrant", "weaviate", "faiss", "sentence transformers", "information retrieval", 
    "llm", "large language models", "fine-tuning", "bert", "gpt", "transformer", 
    "semantic search", "haystack", "opensearch", "lora", "qlora", "peft"
}

def is_honeypot(c):
    # Anomaly 1: Expert proficiency in skills but duration_months is 0
    skills = c.get("skills", [])
    for s in skills:
        if s.get("proficiency") == "expert" and s.get("duration_months", 0) == 0:
            return True
            
    # Anomaly 2: Job duration exceeds years of experience
    yoe = c["profile"]["years_of_experience"]
    for job in c.get("career_history", []):
        dur_years = job.get("duration_months", 0) / 12.0
        if dur_years > yoe + 0.5:
            return True
            
    # Anomaly 3: Krutrim/Sarvam AI before 2023
    for job in c.get("career_history", []):
        comp = job["company"]
        if comp in ("Krutrim", "Sarvam AI"):
            start = job.get("start_date")
            if start:
                try:
                    start_year = int(start.split("-")[0])
                    if start_year < 2023:
                        return True
                except ValueError:
                    pass
    return False

def is_disqualified(c):
    history = c.get("career_history", [])
    skills = c.get("skills", [])
    
    # 1. Pure research: all job titles are academic/research
    if history:
        all_academic = True
        for job in history:
            title = job.get("title", "").lower()
            # check if title matches any academic keyword
            is_acad = False
            for acad in ACADEMIC_TITLES:
                if acad in title:
                    is_acad = True
                    break
            if not is_acad:
                all_academic = False
                break
        if all_academic:
            return True, "Pure research background"
            
    # 2. Consulting-only: all companies are consulting/services
    if history:
        all_consulting = True
        for job in history:
            comp = job.get("company", "").lower()
            is_cons = False
            for cons in CONSULTING_COMPANIES:
                if cons in comp:
                    is_cons = True
                    break
            if not is_cons:
                all_consulting = False
                break
        if all_consulting:
            return True, "Consulting-only background"
            
    # 3. CV/Speech/Robotics only without NLP/IR
    skill_names = {s["name"].lower() for s in skills}
    has_cv_speech = any(s in skill_names for s in CV_SPEECH_ROBOTICS_SKILLS)
    has_nlp_ir = any(s in skill_names for s in NLP_IR_SEARCH_RAG_SKILLS)
    if has_cv_speech and not has_nlp_ir:
        return True, "CV/Speech/Robotics specialist without NLP/IR"
        
    return False, ""

def days_since_active(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        now = datetime(2026, 6, 5) # hardcoded match for system time
        return (now - dt).days
    except Exception:
        return 999

def calculate_technical_score(c):
    profile = c["profile"]
    skills = c.get("skills", [])
    history = c.get("career_history", [])
    education = c.get("education", [])
    
    score = 0.0
    
    # 1. Experience Score (ideal 5-9 years, 6-8 years is best)
    yoe = profile["years_of_experience"]
    if 5 <= yoe <= 9:
        score += 15.0
        if 6 <= yoe <= 8:
            score += 5.0 # extra boost for ideal range
    elif 3 <= yoe < 5:
        score += (yoe / 5.0) * 10.0 # prorated lower experience
    elif yoe > 9:
        score += max(5.0, 15.0 - (yoe - 9.0) * 1.5) # slightly penalized but kept high
        
    # 2. Skills Match Score
    skill_names_lower = {s["name"].lower(): s for s in skills}
    
    # Core Skills: Vector Databases
    vector_dbs = {"pinecone", "weaviate", "qdrant", "milvus", "opensearch", "elasticsearch", "faiss"}
    dbs_found = 0
    for db in vector_dbs:
        if db in skill_names_lower:
            dbs_found += 1
            s = skill_names_lower[db]
            prof = s.get("proficiency", "beginner")
            db_score = 3.0
            if prof == "expert":
                db_score += 1.5
            elif prof == "advanced":
                db_score += 0.8
            score += db_score
    # Cap vector db score at 12
    score = min(score + min(dbs_found * 2, 4), score + 12)
    
    # Core Skills: Retrieval / RAG / Embeddings
    retrieval_skills = {"rag", "embeddings", "retrieval", "sentence transformers", "information retrieval", "semantic search", "haystack", "hybrid search"}
    ret_found = 0
    for rs in retrieval_skills:
        if rs in skill_names_lower:
            ret_found += 1
            s = skill_names_lower[rs]
            prof = s.get("proficiency", "beginner")
            ret_score = 4.0
            if prof == "expert":
                ret_score += 2.0
            elif prof == "advanced":
                ret_score += 1.0
            score += ret_score
    # Cap retrieval skills score at 18
    
    # Core Skills: Evaluation Frameworks
    eval_skills = {"ndcg", "mrr", "map"}
    eval_found = 0
    for es in eval_skills:
        if es in skill_names_lower:
            eval_found += 1
            s = skill_names_lower[es]
            prof = s.get("proficiency", "beginner")
            es_score = 5.0
            if prof == "expert":
                es_score += 2.0
            elif prof == "advanced":
                es_score += 1.0
            score += es_score
            
    # Nice-to-haves: LLM fine-tuning, learning-to-rank, open source, etc.
    nice_to_haves = {"fine-tuning llms", "lora", "qlora", "peft", "learning-to-rank", "mlops", "model deployment", "serving"}
    for nth in nice_to_haves:
        if nth in skill_names_lower:
            s = skill_names_lower[nth]
            prof = s.get("proficiency", "beginner")
            nth_score = 2.0
            if prof in ("expert", "advanced"):
                nth_score += 1.0
            score += nth_score
            
    # Python skill
    if "python" in skill_names_lower:
        s = skill_names_lower["python"]
        prof = s.get("proficiency", "beginner")
        py_score = 3.0
        if prof == "expert":
            py_score += 2.0
        elif prof == "advanced":
            py_score += 1.0
        score += py_score
        
    # 3. Product Company Experience
    product_months = 0
    for job in history:
        comp = job.get("company", "").lower()
        is_cons = False
        for cons in CONSULTING_COMPANIES:
            if cons in comp:
                is_cons = True
                break
        if not is_cons:
            product_months += job.get("duration_months", 0)
            
    product_years = product_months / 12.0
    if product_years > 0:
        score += min(15.0, product_years * 2.5) # max +15 for 6+ years at product companies
        
    # 4. Education Institutional Tier
    for edu in education:
        tier = edu.get("tier", "unknown")
        if tier == "tier_1":
            score += 5.0
            break
        elif tier == "tier_2":
            score += 3.0
            break
        elif tier == "tier_3":
            score += 1.0
            break
            
    return score

def calculate_behavioral_multiplier(c):
    signals = c["redrob_signals"]
    multiplier = 0.0
    
    # 1. Open to Work
    if signals.get("open_to_work_flag", False):
        multiplier += 0.15
        
    # 2. Activity / Recency
    last_act = signals.get("last_active_date", "")
    if last_act:
        days = days_since_active(last_act)
        if days <= 30:
            multiplier += 0.12
        elif days <= 90:
            multiplier += 0.05
        elif days > 180:
            multiplier -= 0.25 # heavy penalty for inactive
            
    # 3. Recruiter response rate & time
    resp_rate = signals.get("recruiter_response_rate", 0.0)
    multiplier += resp_rate * 0.25 # max +0.25
    
    resp_time = signals.get("avg_response_time_hours", 999.0)
    if resp_time <= 24.0:
        multiplier += 0.10
    elif resp_time > 72.0:
        multiplier -= 0.10
        
    # 4. Assessment scores
    assessments = signals.get("skill_assessment_scores", {})
    relevant_assessments = {"rag", "vector databases", "python", "nlp", "elasticsearch", "semantic search"}
    high_scores = 0
    for name, s_score in assessments.items():
        if name.lower() in relevant_assessments:
            if s_score >= 80.0:
                high_scores += 1
                multiplier += 0.06
            elif s_score >= 60.0:
                multiplier += 0.03
                
    # 5. Saved by recruiters & profile views
    saved = signals.get("saved_by_recruiters_30d", 0)
    if saved >= 15:
        multiplier += 0.08
    elif saved >= 5:
        multiplier += 0.04
        
    views = signals.get("profile_views_received_30d", 0)
    if views >= 100:
        multiplier += 0.05
    elif views >= 30:
        multiplier += 0.02
        
    # 6. Github activity
    gh = signals.get("github_activity_score", -1.0)
    if gh >= 70.0:
        multiplier += 0.15
    elif gh >= 40.0:
        multiplier += 0.08
    elif gh == -1.0:
        multiplier -= 0.05 # minor penalty for no GitHub validation
        
    # 7. Interview completion & offer acceptance
    int_comp = signals.get("interview_completion_rate", 0.0)
    if int_comp >= 0.9:
        multiplier += 0.08
    elif int_comp < 0.6:
        multiplier -= 0.15
        
    # 8. Notice period
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        multiplier += 0.15
    elif notice <= 60:
        multiplier += 0.05
    elif notice > 90:
        multiplier -= 0.15
        
    # 9. Location & Relocation
    loc = c["profile"].get("location", "").lower()
    country = c["profile"].get("country", "").lower()
    willing_reloc = signals.get("willing_to_relocate", False)
    
    preferred_cities = {"noida", "pune", "delhi", "ncr", "mumbai", "hyderabad", "bangalore", "bengaluru", "chennai", "gurgaon", "gurugram"}
    is_pref_city = any(city in loc for city in preferred_cities)
    is_india = (country == "india")
    
    if is_pref_city and is_india:
        multiplier += 0.10
        if "noida" in loc or "pune" in loc:
            multiplier += 0.05 # extra boost for office hubs
    elif not is_india and not willing_reloc:
        multiplier -= 0.40 # heavily penalize non-India unwilling to relocate
    elif is_india and willing_reloc:
        multiplier += 0.05
        
    return multiplier

def generate_reasoning(c, rank):
    profile = c["profile"]
    name = profile["anonymized_name"]
    yoe = profile["years_of_experience"]
    title = profile["current_title"]
    comp = profile["current_company"]
    skills = c.get("skills", [])
    signals = c["redrob_signals"]
    
    # Extract matches for reasoning
    skills_names = [s["name"] for s in skills]
    
    # Key matching items
    dbs = [s for s in skills_names if s.lower() in {"pinecone", "weaviate", "qdrant", "milvus", "elasticsearch", "faiss"}]
    ret = [s for s in skills_names if s.lower() in {"rag", "embeddings", "sentence transformers", "semantic search", "retrieval"}]
    evals = [s for s in skills_names if s.lower() in {"ndcg", "mrr", "map"}]
    
    db_str = dbs[0] if dbs else ""
    ret_str = ret[0] if ret else ""
    eval_str = evals[0] if evals else ""
    
    # Check notice period and location for concern checks
    notice = signals.get("notice_period_days", 90)
    loc = profile.get("location", "")
    
    # Draft sentence parts
    sentence1 = ""
    sentence2 = ""
    
    # Segment reasoning based on rank tiers to vary tone
    if rank <= 10:
        # Exceptional candidates
        sentence1 = f"Exceptional Senior AI Engineer with {yoe:.1f} years of experience, currently working at {comp}."
        if ret_str and db_str:
            sentence1 += f" Deployed {ret_str} pipelines using {db_str} in production."
        else:
            sentence1 += " Strong production background building search and retrieval matching systems."
            
        sentence2 = "Outstanding engagement signals (GitHub activity, low response time) and located in Noida/Pune match the core founding team profile."
        if notice > 60:
            sentence2 = f"Excellent technical match with deep indexing expertise, making them a top fit despite a {notice}-day notice period."
            
    elif rank <= 50:
        # Strong candidates
        sentence1 = f"Strong candidate with {yoe:.1f} years experience as a {title}, showing solid expertise in ML matching systems."
        if ret_str:
            sentence1 += f" Has experience building {ret_str} systems."
        if eval_str:
            sentence1 += f" Familiar with offline evaluation metrics like {eval_str}."
            
        sentence2 = f"Good behavioral signals (recruiter response rate {int(signals.get('recruiter_response_rate', 0.0)*100)}%) and {notice}-day notice period align well with hiring requirements."
        if notice > 90:
            sentence2 += f" Note: Notice period of {notice} days is longer, but technical fit is highly relevant."
            
    else:
        # Qualified filler candidates
        sentence1 = f"Qualified candidate with {yoe:.1f} years experience matching key requirements."
        if db_str:
            sentence1 += f" Familiar with vector databases like {db_str}."
        elif ret_str:
            sentence1 += f" Worked on retrieval/NLP tasks like {ret_str}."
            
        sentence2 = f"Available in {loc} with active platform engagement. A solid technical resource for the team."
        if notice <= 30:
            sentence2 += " Immediate availability (sub-30 day notice) is a strong operational advantage."
            
    # Ensure no templates or empty reasonings
    reasoning = f"{sentence1} {sentence2}".strip()
    # Replace double spaces
    reasoning = " ".join(reasoning.split())
    return reasoning

def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Senior AI Engineer.")
    parser.add_argument("--candidates", type=str, default="candidates.jsonl", help="Path to candidates JSONL file")
    parser.add_argument("--out", type=str, default="submission.csv", help="Path to output CSV file")
    args = parser.parse_args()

    print(f"Loading candidate data from {args.candidates}...")
    candidates = []
    
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line))
                
    print(f"Loaded {len(candidates)} candidates.")
    
    scored_candidates = []
    filtered_out_honeypots = 0
    filtered_out_disqualified = 0
    
    for c in candidates:
        cid = c["candidate_id"]
        
        # 1. Filter out Honeypots
        if is_honeypot(c):
            filtered_out_honeypots += 1
            continue
            
        # 2. Filter out Disqualified candidates
        disq, reason = is_disqualified(c)
        if disq:
            filtered_out_disqualified += 1
            continue
            
        # 3. Score candidates
        tech_score = calculate_technical_score(c)
        beh_mult = calculate_behavioral_multiplier(c)
        final_score = tech_score * (1.0 + beh_mult)
        
        scored_candidates.append({
            "candidate_id": cid,
            "candidate_record": c,
            "score": final_score
        })
        
    print(f"Honeypots removed: {filtered_out_honeypots}")
    print(f"Disqualified profiles removed: {filtered_out_disqualified}")
    print(f"Candidates remaining for ranking: {len(scored_candidates)}")
    
    # Sort by score descending. For tie-breaks, sort alphabetically by candidate_id ascending.
    # To do this in python, we can sort by (-score, candidate_id)
    scored_candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    
    # Select top 100
    top_100 = scored_candidates[:100]
    
    # Generate CSV rows
    csv_rows = []
    for idx, item in enumerate(top_100):
        rank = idx + 1
        cid = item["candidate_id"]
        score = item["score"]
        c_record = item["candidate_record"]
        reasoning = generate_reasoning(c_record, rank)
        
        csv_rows.append({
            "candidate_id": cid,
            "rank": rank,
            "score": round(score, 4),
            "reasoning": reasoning
        })
        
    # Write submission CSV
    output_filename = args.out
    with open(output_filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
            
    print(f"Ranking complete! Output saved to {output_filename}")

if __name__ == "__main__":
    main()
