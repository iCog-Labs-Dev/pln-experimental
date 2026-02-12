import re
import sys
import time
import math
import networkx as nx
from collections import defaultdict

try:
    from tqdm import tqdm
    USE_TQDM = True
except ImportError:
    USE_TQDM = False

from sentence_transformers import SentenceTransformer, util

# ---------------- CONFIG ---------------- #

SIM_EDGE_THRESHOLD = 0.45
SIM_PATH_DROP_TOLERANCE = 0.05
MAX_PATH_LEN = 6
MODEL_NAME = "all-MiniLM-L6-v2"

# ---------------- UTILS ---------------- #

def log(msg):
    print(msg, flush=True)

# ---------------- LOAD MODEL ---------------- #

log("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)
_embedding_cache = {}

def embed(concept):
    if concept not in _embedding_cache:
        _embedding_cache[concept] = model.encode(
            concept.replace("_", " "),
            normalize_embeddings=True
        )
        if len(_embedding_cache) % 500 == 0:
            log(f"  cached embeddings: {len(_embedding_cache)}")
    return _embedding_cache[concept]

def similarity(a, b):
    return float(util.cos_sim(embed(a), embed(b)))

# ---------------- PARSER ---------------- #

EDGE_PATTERN = re.compile(
    r"\(:\s+([^\s]+)\s+\(≞\s+\(→\s+([^\s]+)\s+([^\s]+)\s+\(\)\)\s+\(stv\s+[0-9.]+\s+[0-9.]+\)\)\)"
)

def parse_kb(path):
    log("Parsing KB...")
    text = open(path).read()

    edges = []
    atoms = []

    matches = list(EDGE_PATTERN.finditer(text))
    log(f"Found {len(matches)} atoms")

    it = tqdm(matches) if USE_TQDM else matches
    for m in it:
        atom = m.group(0)
        child = m.group(2)
        parent = m.group(3)
        edges.append((child, parent))
        atoms.append((child, parent, atom))

    return edges, atoms

# ---------------- GRAPH ---------------- #

def build_graph(edges):
    log("Building graph...")
    g = nx.DiGraph()
    for c, p in edges:
        if c != p:
            g.add_edge(c, p)
    log(f"Graph nodes: {g.number_of_nodes()}, edges: {g.number_of_edges()}")
    return g

# ---------------- VALIDATION ---------------- #

def structurally_valid(path):
    return len(path) >= 2 and len(set(path)) == len(path)

def edge_semantically_valid(child, parent):
    return similarity(child, parent) >= SIM_EDGE_THRESHOLD

def path_semantically_valid(path):
    root = path[0]
    sims = [similarity(root, n) for n in path]

    for i in range(len(sims) - 1):
        if sims[i+1] > sims[i] + SIM_PATH_DROP_TOLERANCE:
            return False, "semantic abstraction jump"

    return True, None

# ---------------- PATH GENERATION ---------------- #
def generate_paths_upward(g):
    log("Generating upward abstraction paths...")

    all_paths = []

    nodes = list(g.nodes)
    node_iter = tqdm(nodes) if USE_TQDM else nodes

    for idx, start in enumerate(node_iter):
        stack = [(start, [start])]

        while stack:
            node, path = stack.pop()

            if len(path) > MAX_PATH_LEN:
                continue

            parents = list(g.successors(node))
            if not parents:
                all_paths.append(path)
                continue

            for p in parents:
                if p in path:
                    continue

                # early semantic pruning (Level 2)
                if similarity(path[0], p) < SIM_EDGE_THRESHOLD:
                    continue

                new_path = path + [p]
                all_paths.append(new_path)
                stack.append((p, new_path))

        if not USE_TQDM and idx % 500 == 0:
            log(f"  processed roots: {idx}/{len(nodes)}")

    log(f"Generated {len(all_paths)} upward paths")
    return all_paths


# ---------------- MAIN ANALYSIS ---------------- #

def analyze_kb(kb_path):
    edges, atoms = parse_kb(kb_path)
    g = build_graph(edges)

    valid_paths = []
    invalid_paths = []

    edge_support = defaultdict(int)
    edge_reject_reason = defaultdict(list)

    paths = generate_paths_upward(g)

    log("Validating paths...")

    it = tqdm(paths) if USE_TQDM else paths
    start = time.time()

    for idx, path in enumerate(it):
        if not structurally_valid(path):
            invalid_paths.append((path, "structural violation"))
            continue

        bad_edge = False
        for i in range(len(path) - 1):
            if not edge_semantically_valid(path[i], path[i+1]):
                edge_reject_reason[(path[i], path[i+1])].append("low semantic similarity")
                invalid_paths.append((path, "edge semantic failure"))
                bad_edge = True
                break

        if bad_edge:
            continue

        ok, reason = path_semantically_valid(path)
        if not ok:
            for i in range(len(path) - 1):
                edge_reject_reason[(path[i], path[i+1])].append(reason)
            invalid_paths.append((path, reason))
            continue

        valid_paths.append(path)
        for i in range(len(path) - 1):
            edge_support[(path[i], path[i+1])] += 1

        if not USE_TQDM and idx % 500 == 0 and idx > 0:
            elapsed = time.time() - start
            log(f"  validated {idx}/{len(paths)} paths ({elapsed:.1f}s elapsed)")

    return valid_paths, invalid_paths, edge_support, edge_reject_reason, atoms

# ---------------- OUTPUT ---------------- #

def write_paths(path, paths):
    log(f"Writing {path}...")
    with open(path, "w") as f:
        for p in paths:
            if isinstance(p, tuple):
                f.write(" -> ".join(p[0]) + " | " + p[1] + "\n")
            else:
                f.write(" -> ".join(p) + "\n")

def write_clean_kb(path, atoms, edge_support, edge_reasons):
    log(f"Writing cleaned KB to {path}...")
    with open(path, "w") as f:
        for child, parent, atom in atoms:
            if edge_support.get((child, parent), 0) > 0:
                f.write(atom + "\n")
            else:
                reasons = set(edge_reasons.get((child, parent), ["no valid abstraction path"]))
                f.write(f"; REMOVED ({child} -> {parent}) because: {', '.join(reasons)}\n")

# ---------------- CLI ---------------- #

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clean_kb.py <kb_file>")
        sys.exit(1)

    kb = sys.argv[1]

    log("Starting KB analysis...")
    valid, invalid, support, reasons, atoms = analyze_kb(kb)

    write_paths("valid_paths.txt", valid)
    write_paths("invalid_paths.txt", invalid)
    write_clean_kb("cleaned_kb.mm", atoms, support, reasons)

    log("Done.")
    log(f"Valid paths: {len(valid)}")
    log(f"Invalid paths: {len(invalid)}")
