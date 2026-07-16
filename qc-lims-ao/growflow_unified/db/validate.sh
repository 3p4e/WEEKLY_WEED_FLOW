#!/bin/sh
# Throwaway validation of the converged GrowFlow Unified data layer.
# Spins a disposable pgvector/pg17 container, applies every migration in order,
# and asserts the adaptive tree + extensible attributes + governance seed.
# Usage: sh validate.sh [DB_DIR]   (DB_DIR defaults to this script's directory)
DBDIR="${1:-$(cd "$(dirname "$0")" && pwd)}"
C=gf_pgtest
docker rm -f $C >/dev/null 2>&1 || true
docker run -d --name $C -e POSTGRES_PASSWORD=test pgvector/pgvector:pg17 >/dev/null
for i in $(seq 1 40); do docker exec $C pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
for f in 0000_schema 0002_enrich 0004_adaptive 0003_import_qc 0005_agents 0006_auth_rls 0007_hierarchy 0008_password_reset; do
  if cat "$DBDIR/$f.sql" | docker exec -i $C psql -U postgres -q -v ON_ERROR_STOP=1 -d postgres >/tmp/o 2>&1; then echo "$f PASS"; else echo "$f FAIL:"; tail -8 /tmp/o; fi
done
P(){ docker exec $C psql -U postgres -d postgres -tAc "$1"; }
echo "--- nodes by kind ---"; docker exec $C psql -U postgres -d postgres -c "select node_kind, count(*) from planner_task group by node_kind order by 2 desc"
echo "--- adaptive tree depth (0=root) ---"; docker exec $C psql -U postgres -d postgres -c "WITH RECURSIVE tr AS (SELECT id,parent_id,0 d FROM planner_task WHERE parent_id IS NULL UNION ALL SELECT c.id,c.parent_id,tr.d+1 FROM planner_task c JOIN tr ON c.parent_id=tr.id) SELECT d AS depth, count(*) FROM tr GROUP BY d ORDER BY d"
echo "total nodes:          $(P "select count(*) from planner_task")"
echo "orphans (bad parent): $(P "select count(*) from planner_task c where c.parent_id is not null and not exists(select 1 from planner_task p where p.id=c.parent_id)")"
echo "all owned by Head-of-QC: $(P "select (count(*)=count(*) filter (where owner_id=(select id from app_user where username='blagoj'))) from planner_task")"
echo "is_sop tasks:         $(P "select count(*) from planner_task where is_sop")"
echo "annex_count sum:      $(P "select coalesce(sum(annex_count),0) from planner_task")"
echo "ended_at >= started:  $(P "select count(*) from planner_task where ended_at is not null and ended_at>=started_at")/$(P "select count(*) from planner_task where ended_at is not null")"
echo "--- ADAPTIVE LAYER ---"
echo "tasks w/ attributes:  $(P "select count(*) from planner_task where attributes <> '{}'::jsonb")"
echo "attribute keys:       $(P "select string_agg(distinct k,', ' order by k) from planner_task, jsonb_object_keys(attributes) k")"
echo "field_registry rows:  $(P "select count(*) from field_registry")"
echo "attributes GIN index: $(P "select count(*) from pg_indexes where indexname='idx_planner_task_attrs'")"
echo "--- AGENT ECOSYSTEM (P2) ---"
echo "ai_agent_bindings:    $(P "select count(*) from ai_agent_bindings") rows, $(P "select count(*) from ai_agent_bindings where is_active") active"
echo "bound functions:      $(P "select string_agg(function_key,', ' order by function_key) from ai_agent_bindings")"
echo "change_proposal seed: $(P "select count(*) from change_proposal where status='pending'") pending"
docker exec $C psql -U postgres -d postgres -c "select proposed_by, kind, target, status from change_proposal"
echo "--- depth-3 lifecycle sample (SOP annex -> Draft/Review/Approve) ---"
docker exec $C psql -U postgres -d postgres -c "select substr(p.title,1,22) annex, s.title step, s.status from planner_task s join planner_task p on s.parent_id=p.id where s.node_kind='step' order by p.title, (s.attributes->>'position')::int limit 6"
docker rm -f $C >/dev/null 2>&1 || true
echo DONE
