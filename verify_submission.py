import json
import csv
import sys
import re

def verify():
    print("Running verification checks on submission.csv...")
    errors = []
    
    # 1. Load candidate IDs and honeypots from candidates.jsonl
    all_cids = set()
    hps = set()
    with open("candidates.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            c = json.loads(line)
            cid = c["candidate_id"]
            all_cids.add(cid)
            yoe = c["profile"]["years_of_experience"]
            
            # Honeypot check
            is_hp = False
            if any(s.get("proficiency") == "expert" and s.get("duration_months", 0) == 0 for s in c.get("skills", [])):
                is_hp = True
            if any((job.get("duration_months", 0) / 12.0) > yoe + 0.5 for job in c.get("career_history", [])):
                is_hp = True
            for job in c.get("career_history", []):
                if job["company"] in ("Krutrim", "Sarvam AI"):
                    start = job.get("start_date")
                    if start and int(start.split("-")[0]) < 2023:
                        is_hp = True
            if is_hp:
                hps.add(cid)
                
    # 2. Read submission
    rows = []
    with open("submission.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            
    # Check count
    if len(rows) != 100:
        errors.append(f"Expected exactly 100 rows, found {len(rows)}.")
        
    seen_ids = set()
    seen_ranks = set()
    prev_score = float('inf')
    prev_rank = 0
    prev_cid = ""
    
    for idx, row in enumerate(rows):
        cid = row["candidate_id"]
        rank = int(row["rank"])
        score = float(row["score"])
        reasoning = row["reasoning"]
        
        # Check candidate ID format
        if not re.match(r"^CAND_[0-9]{7}$", cid):
            errors.append(f"Row {idx+2}: Candidate ID {cid} is malformed.")
            
        # Check existence in candidate list
        if cid not in all_cids:
            errors.append(f"Row {idx+2}: Candidate ID {cid} does not exist in candidates.jsonl.")
            
        # Check duplicates
        if cid in seen_ids:
            errors.append(f"Row {idx+2}: Duplicate Candidate ID {cid}.")
        seen_ids.add(cid)
        
        # Check ranks
        if rank != idx + 1:
            errors.append(f"Row {idx+2}: Expected rank {idx+1}, got {rank}.")
        seen_ranks.add(rank)
        
        # Check score monotonicity
        if score > prev_score:
            errors.append(f"Row {idx+2}: Score {score} increases from previous score {prev_score}.")
            
        # Check tie breaks
        if score == prev_score:
            if cid < prev_cid:
                errors.append(f"Row {idx+2}: Tie-break failure. Score is equal to previous, but candidate_id {cid} is alphabetically smaller than {prev_cid}.")
                
        # Check honeypot presence
        if cid in hps:
            errors.append(f"Row {idx+2}: Honeypot candidate {cid} ranked in top 100!")
            
        # Check reasoning
        if not reasoning:
            errors.append(f"Row {idx+2}: Reasoning is empty.")
        elif len(reasoning.strip()) < 10:
            errors.append(f"Row {idx+2}: Reasoning is too short: '{reasoning}'.")
            
        prev_score = score
        prev_rank = rank
        prev_cid = cid
        
    if len(seen_ranks) != 100 or min(seen_ranks) != 1 or max(seen_ranks) != 100:
        errors.append("Ranks must cover exactly 1 to 100.")
        
    if errors:
        print(f"Verification FAILED with {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("Verification PASSED. The CSV is perfectly formatted and free of honeypots!")

if __name__ == "__main__":
    verify()
