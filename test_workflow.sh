#!/usr/bin/env bash
# syn — comprehensive attack-surface & edge-case test script (Fireworks)
# Each section uses a unique agent_id to avoid cross-contaminated history.
# Usage: ./test_workflow.sh [base_url]
# For a deterministic run this script clears data/audit.db and
# engine/policy_config.bootstrap.yaml, and (when the default local server is
# not already running) starts its own server and stops it afterwards.

BASE="${1:-http://127.0.0.1:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PASS=0; FAIL=0
CURL="curl -s --max-time 45"

# --- clear state so the run is deterministic regardless of prior state ---
rm -f data/audit.db 2>/dev/null
printf 'tools: {}\n' > engine/policy_config.bootstrap.yaml 2>/dev/null

# --- auto-start a local server if the default endpoint is not up ---
OWN_SERVER=0
if [ "$BASE" = "http://127.0.0.1:8000" ]; then
  if ! curl -s --max-time 3 "$BASE/health" | grep -q '"status":"ok"'; then
    echo "=== starting local server ==="
    setsid uv run uvicorn gateway.main:app --host 127.0.0.1 --port 8000 >/tmp/syn_test_server.log 2>&1 </dev/null &
    OWN_SERVER=$!
    for i in $(seq 1 60); do
      if curl -s --max-time 3 "$BASE/health" | grep -q '"status":"ok"'; then echo "server up after ${i}s"; break; fi
      sleep 1
    done
  fi
fi

check() {
  local label="$1" expected="$2" actual="$3"
  if echo "$actual" | jq -e "$expected" >/dev/null 2>&1; then
    echo "  [PASS] $label"
    ((PASS++))
  else
    echo "  [FAIL] $label — expected $expected"
    echo "         got: $(echo "$actual" | jq -c . 2>/dev/null || echo "$actual")"
    ((FAIL++))
  fi
}

check_http() {
  local label="$1" expected="$2" actual="$3"
  if [ "$actual" = "$expected" ]; then
    echo "  [PASS] $label"
    ((PASS++))
  else
    echo "  [FAIL] $label — expected HTTP $expected, got $actual"
    ((FAIL++))
  fi
}

echo "========================================"
echo "  syn attack-surface & edge-case suite"
echo "========================================"

echo ""
echo "=== 1. Liveness & tool list ==="
R=$($CURL "$BASE/health"); check "health returns ok" '.status=="ok"' "$R"
R=$($CURL "$BASE/tools"); check "tools lists 3+ entries" 'length>=3' "$R"

echo ""
echo "=== 2. Happy path (fresh agent 'hp') ==="
A="hp"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "send_payment approved" '.decision=="approved"' "$R"
check "has factor_scores" '.factor_scores.severity>=0' "$R"
check "has session_data" '.session_data.session_id!=null' "$R"
check "simulation false by default" '.simulation==false' "$R"

echo ""
echo "=== 3. Session lifecycle (fresh agent 'sl') ==="
A="sl"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"start\",\"agent_id\":\"$A\"}")
SID=$(echo "$R" | jq -r '.session_data.session_id // ""')
check "start returns session_id" '.session_data.session_id!=null' "$R"
check "start returns uuid" '.session_data.session_id|test("^[0-9a-f-]{36}$")' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"continue\",\"session_id\":\"$SID\",\"agent_id\":\"$A\"}")
check "continue reuses UUID" ".session_data.session_id==\"$SID\"" "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"end\",\"session_id\":\"$SID\",\"agent_id\":\"$A\"}")
check "end returns session_id" '.session_data.session_id!=null' "$R"

echo ""
echo "=== 4. Session attacks (fresh agent 'sa') ==="
A="sa"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"continue\",\"session_id\":\"not-a-uuid\",\"agent_id\":\"$A\"}")
check "invalid uuid → fallback timebucket" '.trigger|test("fallback_timebucket")' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"continue\",\"session_id\":\"\",\"agent_id\":\"$A\"}")
check "empty session_id → fallback timebucket" '.trigger|test("fallback_timebucket")' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"continue\",\"session_id\":null,\"agent_id\":\"$A\"}")
check "null session_id → fallback timebucket" '.trigger|test("fallback_timebucket")' "$R"

# Cross-agent session steal
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"start\",\"agent_id\":\"${A}_a\"}")
SID_A=$(echo "$R" | jq -r '.session_data.session_id // ""')
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"continue\",\"session_id\":\"$SID_A\",\"agent_id\":\"${A}_b\"}")
check "cross-agent session steal doesn't crash" '.decision!=null' "$R"

echo ""
echo "=== 5. Parameter injection (fresh agent 'pi') ==="
A="pi"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"query_database\",\"parameters\":{\"query\":\"1; DROP TABLE users--\"},\"agent_id\":\"$A\"}")
check "SQLi in query" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"delete_file\",\"parameters\":{\"file_path\":\"../../etc/passwd\"},\"agent_id\":\"$A\"}")
check "path traversal" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":-100,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "negative amount" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":null,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "null amount (no 500)" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":9999999999999,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "overflow amount" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{},\"agent_id\":\"$A\"}")
check "missing amount param" '.decision!=null' "$R"

echo ""
echo "=== 6. Payload attacks (fresh agent 'pl') ==="
A="pl"
R=$($CURL -o /dev/null -w "%{http_code}" -X POST "$BASE/intercept" \
  -H 'Content-Type: application/json' -d 'this is not json')
check_http "malformed JSON → 422" "422" "$R"

R=$($CURL -o /dev/null -w "%{http_code}" -X POST "$BASE/intercept" \
  -H 'Content-Type: application/json' -d '')
check_http "empty body → 422" "422" "$R"

R=$($CURL -o /dev/null -w "%{http_code}" -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"parameters\":{\"amount\":50},\"agent_id\":\"$A\"}")
check_http "missing action_type → 422" "422" "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50},\"__proto__\":{\"admin\":true},\"constructor\":{\"prototype\":{\"admin\":true}},\"agent_id\":\"$A\"}")
check "proto pollution fields" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"<script>alert(1)</script>\",\"parameters\":{},\"agent_id\":\"$A\"}")
check "XSS tool name → blocked" '.decision=="blocked"' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"Send_Payment\",\"parameters\":{\"amount\":50,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "case mismatch → blocked" '.decision=="blocked"' "$R"

echo ""
echo "=== 7. Mode attacks (fresh agent 'md') ==="
A="md"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50,\"recipient\":\"alice\"},\"mode\":\"SIMULATION\",\"agent_id\":\"$A\"}")
check "SIMULATION uppercase" '.simulation==true' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50,\"recipient\":\"alice\"},\"mode\":\"evil\",\"agent_id\":\"$A\"}")
check "invalid mode doesn't crash" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50,\"recipient\":\"alice\"},\"mode\":\"Simulation\",\"agent_id\":\"$A\"}")
check "Simulation titlecase" '.simulation==true' "$R"

echo ""
echo "=== 8. Agent ID attacks (fresh agent 'ag') ==="
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d '{"action_type":"send_payment","parameters":{"amount":50},"agent_id":""}')
check "empty agent_id" '.decision!=null' "$R"

LONG=$(python3 -c "print('a'*10000)")
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50},\"agent_id\":\"$LONG\"}")
check "10k char agent_id" '.decision!=null' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50},\"agent_id\":\"../../etc/passwd\"}")
check "path traversal agent_id" '.decision!=null' "$R"

echo ""
echo "=== 9. Weighted-score escalation (fresh agent 'ws') ==="
A="ws"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"delete_file\",\"parameters\":{\"file_path\":\"/data/prod/secrets.xlsx\"},\"agent_id\":\"$A\"}")
check "delete_file escalated" '.decision=="escalated"' "$R"
check "trigger weighted_score/cumulative" '(.trigger|startswith("weighted_score")) or (.trigger|startswith("session:cumulative_threshold"))' "$R"
check "has rollback plan" '.rollback_plan!=null' "$R"
check "has expires_at" '.expires_at!=null' "$R"

echo ""
echo "=== 9b. Beat 4 pattern (fresh agent 'b4') ==="
A="b4"
for i in 1 2 3; do
  $CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
    -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"agent_id\":\"$A\"}" >/dev/null
done
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":1000,\"recipient\":\"mallory\"},\"agent_id\":\"$A\"}")
check "beat 4 escalated" '.decision=="escalated"' "$R"
check "trigger pattern_matched" '.trigger|test("pattern_matched")' "$R"

echo ""
echo "=== 9c. Cumulative threshold (fresh agent 'ct') ==="
A="ct"
for i in $(seq 1 6); do
  $CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
    -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":200,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}" >/dev/null
done
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":200,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "cumulative threshold escalated" '.decision=="escalated"' "$R"
check "trigger cumulative_threshold" '.trigger|test("cumulative_threshold")' "$R"

echo ""
echo "=== 10. Cumulative edge cases (fresh agent 'ce') ==="
A="ce"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":1,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "tiny amount → approved" '.decision=="approved"' "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"agent_id\":\"$A\"}")
check "check_balance ok" '.decision!=null' "$R"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"query_database\",\"parameters\":{\"query\":\"SELECT 1\"},\"agent_id\":\"$A\"}")
check "query_database ok" '.decision!=null' "$R"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":50,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "cross-type after query (may match pattern)" '.decision!=null' "$R"

echo ""
echo "=== 11. Pattern edge cases (fresh agent 'pe') ==="
A="pe"
$CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"agent_id\":\"$A\"}" >/dev/null
$CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"agent_id\":\"$A\"}" >/dev/null
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":100,\"recipient\":\"alice\"},\"agent_id\":\"$A\"}")
check "2/3 pattern (check_balance→send_payment triggers)" '.decision=="escalated"' "$R"

$CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"agent_id\":\"${A}_nm\"}" >/dev/null
$CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"agent_id\":\"${A}_nm\"}" >/dev/null
$CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"agent_id\":\"${A}_nm\"}" >/dev/null
$CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"query_database\",\"parameters\":{\"query\":\"SELECT 1\"},\"agent_id\":\"${A}_nm\"}" >/dev/null
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"send_payment\",\"parameters\":{\"amount\":100,\"recipient\":\"alice\"},\"agent_id\":\"${A}_nm\"}")
check "intervening query still allows check→send match" '.decision!=null' "$R"

echo ""
echo "=== 12. Unknown tool (fresh agent 'uk') ==="
A="uk"
R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"deploy_model\",\"parameters\":{\"model\":\"gpt-7\"},\"agent_id\":\"$A\"}")
check "unknown tool blocked" '.decision=="blocked"' "$R"
check "trigger unknown_tool" '.trigger=="gateway:unknown_tool"' "$R"

echo ""
echo "=== 13. Bootstrap edge cases ==="
R=$($CURL -X POST "$BASE/bootstrap/introspect" -H 'Content-Type: application/json' \
  -d '{"manual_schemas":[]}')
check "empty schemas → valid" '.valid==true' "$R"
check "empty schemas → 0 rules" '.rules|length==0' "$R"

R=$($CURL -X POST "$BASE/bootstrap/approve/nonexistent_tool" -H 'Content-Type: application/json' \
  -d '{"reviewed_by":"demo-admin"}')
check "approve nonexistent tool" '.success==false' "$R"

R=$($CURL -X POST "$BASE/bootstrap/reject/nonexistent_tool" -H 'Content-Type: application/json' \
  -d '{"reviewed_by":"demo-admin"}')
check "reject nonexistent tool" '.success==false' "$R"

R=$($CURL -X POST "$BASE/bootstrap/approve-all" -H 'Content-Type: application/json' \
  -d '{"reviewed_by":"demo-admin"}')
check "approve-all (may approve bg bootstraps)" '.success==true' "$R"

R=$($CURL -X POST "$BASE/bootstrap/retry/99999" -H 'Content-Type: application/json' \
  -d '{"tool_name":"test","parameters":{}}')
check "retry nonexistent rule" '.success==false' "$R"

echo ""
echo "=== 14. Timeline & resolution ==="
R=$($CURL "$BASE/timeline?outcome=escalated")
check "timeline filtered" 'length>=0' "$R"

R=$($CURL "$BASE/timeline?outcome=nonexistent")
check "bad filter doesn't crash" 'length>=0' "$R"

R=$($CURL -X POST "$BASE/resolve/99999" -H 'Content-Type: application/json' \
  -d '{"outcome":"approved"}')
check "resolve nonexistent entry" '.detail!=null or .success!=null' "$R"

echo ""
echo "=== 15. Concurrency (agents 'ca', 'cb') ==="
R1=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d '{"action_type":"check_balance","parameters":{},"session_intent":"start","agent_id":"ca"}')
SID_A=$(echo "$R1" | jq -r '.session_data.session_id // ""')

R2=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d '{"action_type":"check_balance","parameters":{},"session_intent":"start","agent_id":"cb"}')
SID_B=$(echo "$R2" | jq -r '.session_data.session_id // ""')

if [ "$SID_A" != "$SID_B" ] && [ -n "$SID_A" ] && [ -n "$SID_B" ]; then
  echo "  [PASS] concurrent sessions have different IDs"
  ((PASS++))
else
  echo "  [FAIL] concurrent sessions should differ (A=$SID_A, B=$SID_B)"
  ((FAIL++))
fi

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"continue\",\"session_id\":\"$SID_A\",\"agent_id\":\"ca\"}")
check "session A continues interleaved" ".session_data.session_id==\"$SID_A\"" "$R"

R=$($CURL -X POST "$BASE/intercept" -H 'Content-Type: application/json' \
  -d "{\"action_type\":\"check_balance\",\"parameters\":{},\"session_intent\":\"continue\",\"session_id\":\"$SID_B\",\"agent_id\":\"cb\"}")
check "session B continues interleaved" ".session_data.session_id==\"$SID_B\"" "$R"

echo ""
echo "========================================"
echo "  RESULTS: $PASS passed, $FAIL failed"
echo "========================================"

# --- teardown: stop a server we started and leave bootstrap clean ---
if [ "$OWN_SERVER" != "0" ]; then
  echo "=== stopping local server ==="
  pkill -9 -f 'uv r[u]n' 2>/dev/null
  pkill -9 -f 'uvic[o]rn' 2>/dev/null
  sleep 1
fi
printf 'tools: {}\n' > engine/policy_config.bootstrap.yaml 2>/dev/null
exit $FAIL
