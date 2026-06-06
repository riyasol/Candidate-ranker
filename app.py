import http.server
import socketserver
import json
import os
import urllib.parse
from datetime import datetime
import rank_candidates

PORT = 8000

class RankerHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Allow CORS for easier testing
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/rank':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # We expect raw JSON list of candidates, or JSONL payload
                # Let's decode the payload
                payload = post_data.decode('utf-8')
                candidates = []
                
                # Check if payload is a JSON array
                payload_stripped = payload.strip()
                if payload_stripped.startswith('['):
                    candidates = json.loads(payload)
                else:
                    # Try reading as JSONL (one JSON per line)
                    for line in payload.split('\n'):
                        if line.strip():
                            candidates.append(json.loads(line))
                
                print(f"Server received {len(candidates)} candidates for ranking.")
                
                # Run the ranking logic
                scored_candidates = []
                honeypots_count = 0
                disqualified_count = 0
                
                for c in candidates:
                    if rank_candidates.is_honeypot(c):
                        honeypots_count += 1
                        continue
                    disq, reason = rank_candidates.is_disqualified(c)
                    if disq:
                        disqualified_count += 1
                        continue
                        
                    tech_score = rank_candidates.calculate_technical_score(c)
                    beh_mult = rank_candidates.calculate_behavioral_multiplier(c)
                    final_score = tech_score * (1.0 + beh_mult)
                    
                    scored_candidates.append({
                        "candidate_id": c["candidate_id"],
                        "name": c["profile"]["anonymized_name"],
                        "headline": c["profile"]["headline"],
                        "yoe": c["profile"]["years_of_experience"],
                        "current_title": c["profile"]["current_title"],
                        "current_company": c["profile"]["current_company"],
                        "location": c["profile"]["location"],
                        "country": c["profile"]["country"],
                        "score": round(final_score, 4),
                        "tech_score": round(tech_score, 4),
                        "beh_mult": round(beh_mult * 100, 1),
                        "skills": [s["name"] for s in c.get("skills", [])],
                        "notice_period_days": c["redrob_signals"].get("notice_period_days", 90),
                        "open_to_work": c["redrob_signals"].get("open_to_work_flag", False),
                        "github_score": c["redrob_signals"].get("github_activity_score", -1.0),
                        "response_rate": round(c["redrob_signals"].get("recruiter_response_rate", 0.0) * 100, 1),
                        "raw_candidate": c
                    })
                
                # Sort
                scored_candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))
                
                # Take top 100
                top_100 = scored_candidates[:100]
                
                # Add rank and reasoning
                for idx, item in enumerate(top_100):
                    rank = idx + 1
                    item["rank"] = rank
                    item["reasoning"] = rank_candidates.generate_reasoning(item["raw_candidate"], rank)
                    # Remove raw candidate to reduce payload size, except if we want full details
                    # Let's keep a sanitized version for the UI
                    del item["raw_candidate"]
                
                response = {
                    "status": "success",
                    "total_received": len(candidates),
                    "honeypots_removed": honeypots_count,
                    "disqualified_removed": disqualified_count,
                    "ranked_count": len(scored_candidates),
                    "results": top_100
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                print(f"Error processing rank request: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
        else:
            super().do_POST()

def run_server():
    # Make sure we change directory to serve files from the current folder
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # SimpleHTTPRequestHandler serves files from current directory
    handler = RankerHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.server_close()

if __name__ == "__main__":
    run_server()
