# Sunwell Packaging & Distribution Strategy

## Current Architecture

```
┌─────────────────────────────────────────┐
│         Svelte Frontend (UI)            │
└──────────────────┬──────────────────────┘
                   │ IPC (Tauri)
┌──────────────────▼──────────────────────┐
│      Rust/Tauri Backend (Bridge)        │
│  - Spawns subprocesses                  │
│  - Streams NDJSON events                │
│  - File system operations               │
└──────────────────┬──────────────────────┘
                   │ subprocess stdout
┌──────────────────▼──────────────────────┐
│      Python Agent (Core Logic)          │
│  - CLI: `sunwell agent run --json`      │
│  - Requires Python 3.14+                │
│  - Free-threading optimized (3.14t)     │
└─────────────────────────────────────────┘
```

**Current State**: Rust expects `sunwell` CLI in PATH (assumes Python pre-installed)

---

## Packaging Options

### Option 1: Bundle Python with Tauri ⭐ **RECOMMENDED**

**Approach**: Include Python runtime + dependencies in Tauri bundle

**Implementation**:
1. **Build Python distribution** using PyInstaller or Nuitka:
   ```bash
   # Create standalone Python executable
   pyinstaller --onefile --name sunwell-agent \
     --hidden-import sunwell \
     src/sunwell/cli/agent/run.py
   ```

2. **Bundle in Tauri** via `tauri.conf.json`:
   ```json
   {
     "bundle": {
       "resources": [
         "python-runtime/**",
         "sunwell-agent"
       ]
     }
   }
   ```

3. **Update Rust to use bundled Python**:
   ```rust
   // Detect bundled Python vs system Python
   let python_exe = if let Ok(bundled) = app.path().resource("sunwell-agent") {
       bundled
   } else {
       PathBuf::from("sunwell") // Fallback to PATH
   };
   ```

**Pros**:
- ✅ Single installer (~50-100MB total)
- ✅ Works out-of-the-box (no Python setup)
- ✅ Consistent Python version (3.14t)
- ✅ Can still use system Python if available

**Cons**:
- ❌ Larger bundle size
- ❌ More complex build pipeline
- ❌ Platform-specific Python builds needed

**Bundle Size Estimate**:
- Rust + Svelte: ~10-20MB
- Python 3.14t runtime: ~30-50MB
- Sunwell dependencies: ~20-30MB
- **Total: ~60-100MB** (vs Electron's 200MB+)

---

### Option 2: Require Python Pre-install (Current)

**Approach**: Bundle only Rust + Svelte, require `pip install sunwell`

**Pros**:
- ✅ Small bundle (~10-20MB)
- ✅ Simple build
- ✅ Users get Python updates automatically

**Cons**:
- ❌ Installation friction (2-step: install app + install Python)
- ❌ Version conflicts (needs Python 3.14+)
- ❌ Free-threading Python (3.14t) not standard

**Best For**: Developer tools where Python is expected

---

### Option 3: Convert Python → Rust

**Approach**: Rewrite Python agent in Rust

**Pros**:
- ✅ Single language
- ✅ Smaller bundle (~20-30MB total)
- ✅ Better performance (no subprocess overhead)
- ✅ Easier distribution (single binary)

**Cons**:
- ❌ **Massive rewrite** (~10k+ lines of Python)
- ❌ Lose Python ecosystem (numpy, rich, click, etc.)
- ❌ Lose Python 3.14t free-threading benefits
- ❌ Harder to iterate (Rust compile times)
- ❌ AI/ML libraries less mature in Rust

**Effort Estimate**: 3-6 months full-time

**Verdict**: ❌ **Not recommended** - Python is core to Sunwell's value (AI/ML ecosystem, free-threading)

---

### Option 4: Convert Rust → Python

**Approach**: Use Python for everything (Electron-like wrapper)

**Pros**:
- ✅ Single language
- ✅ Easier maintenance
- ✅ Leverage Python ecosystem

**Cons**:
- ❌ **Much larger bundle** (Python + Electron-like runtime = 200MB+)
- ❌ Lose Tauri's benefits (small size, security, native feel)
- ❌ Slower startup (Python interpreter)

**Verdict**: ❌ **Not recommended** - Defeats purpose of choosing Tauri

---

## Recommended Strategy: Hybrid Approach

### Phase 1: Current (Require Python) ✅
- **Now**: Bundle Rust + Svelte only
- **Users**: Install Python separately: `pip install sunwell`
- **Best for**: Early adopters, developers

### Phase 2: Optional Bundling (2024 Q2)
- **Add**: Build script that optionally bundles Python
- **Users choose**: 
  - Download small bundle (requires Python)
  - Download full bundle (includes Python)
- **Best for**: Broader audience

### Phase 3: Default Bundling (2024 Q3)
- **Default**: Bundle Python by default
- **Fallback**: Use system Python if available
- **Best for**: Mainstream users

---

## Implementation Plan: Option 1 (Bundle Python)

### Step 1: Create Python Bundler Script

```bash
# scripts/bundle-python.sh
#!/bin/bash
# Build standalone Python distribution for Tauri

set -e

PLATFORM=$1  # macos, windows, linux
OUT_DIR="studio/src-tauri/resources/python-runtime"

echo "🔨 Building Python runtime for $PLATFORM..."

# Use PyInstaller to create standalone executable
pyinstaller \
  --onefile \
  --name sunwell-agent \
  --hidden-import sunwell \
  --hidden-import sunwell.adaptive \
  --hidden-import sunwell.cli \
  --collect-all sunwell \
  --distpath "$OUT_DIR/$PLATFORM" \
  src/sunwell/cli/agent/run.py

echo "✅ Python runtime bundled to $OUT_DIR/$PLATFORM"
```

### Step 2: Update Tauri Config

```json
{
  "bundle": {
    "resources": [
      "python-runtime/**"
    ],
    "targets": ["all"]
  }
}
```

### Step 3: Update Rust Agent Bridge

```rust
// studio/src-tauri/src/agent.rs

use std::path::{Path, PathBuf};
use tauri::AppHandle;

fn find_sunwell_executable(app: &AppHandle) -> PathBuf {
    // 1. Try bundled Python runtime
    if let Ok(resource_dir) = app.path().resource("python-runtime") {
        #[cfg(target_os = "macos")]
        let bundled = resource_dir.join("macos/sunwell-agent");
        #[cfg(target_os = "windows")]
        let bundled = resource_dir.join("windows/sunwell-agent.exe");
        #[cfg(target_os = "linux")]
        let bundled = resource_dir.join("linux/sunwell-agent");
        
        if bundled.exists() {
            return bundled;
        }
    }
    
    // 2. Try system Python with sunwell module
    if let Ok(python) = which::which("python3.14t") {
        // Check if sunwell is importable
        return PathBuf::from("python3.14t"); // Will use -m sunwell
    }
    
    // 3. Fallback to PATH sunwell CLI
    PathBuf::from("sunwell")
}

impl AgentBridge {
    pub fn run_goal(
        &mut self,
        app: AppHandle,
        goal: &str,
        project_path: &Path,
    ) -> Result<(), String> {
        let sunwell_exe = find_sunwell_executable(&app);
        
        let mut cmd = if sunwell_exe.ends_with("python3.14t") || sunwell_exe.ends_with("python3") {
            // Use Python module
            Command::new(&sunwell_exe)
                .args(["-m", "sunwell", "agent", "run", "--json", "--strategy", "harmonic", goal])
        } else {
            // Use bundled executable
            Command::new(&sunwell_exe)
                .args(["agent", "run", "--json", "--strategy", "harmonic", goal])
        };
        
        // ... rest of implementation
    }
}
```

### Step 4: Update Build Pipeline

```yaml
# .github/workflows/build.yml
name: Build Studio

on:
  release:
    types: [created]

jobs:
  build:
    strategy:
      matrix:
        platform: [macos-latest, windows-latest, ubuntu-latest]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      
      - name: Install dependencies
        run: |
          pip install pyinstaller
          pip install -e ".[all]"
      
      - name: Bundle Python runtime
        run: ./scripts/bundle-python.sh ${{ matrix.platform }}
      
      - name: Build Tauri app
        run: |
          cd studio
          npm install
          npm run tauri build
```

---

## Language Consolidation Analysis

### Should We Convert Python → Rust?

**Answer: ❌ No**

**Reasons**:
1. **Python 3.14t free-threading** is a core differentiator
   - True parallelism without GIL
   - Rust can't replicate this benefit
   
2. **AI/ML ecosystem** is Python-native
   - Ollama Python bindings
   - numpy, sentence-transformers, etc.
   - Rust alternatives are immature

3. **Development velocity**
   - Python: Fast iteration, easy debugging
   - Rust: Compile times, stricter types (good but slower)

4. **Codebase size**
   - ~10k+ lines of Python agent logic
   - 3-6 month rewrite effort
   - High risk, low reward

### Should We Convert Rust → Python?

**Answer: ❌ No**

**Reasons**:
1. **Tauri benefits** would be lost
   - Small bundle size (10MB vs 200MB+)
   - Native security model
   - Fast startup

2. **Rust is minimal** (~500 lines)
   - Just subprocess spawning + IPC
   - Easy to maintain
   - No need to rewrite

3. **Best of both worlds**
   - Rust: Thin shell layer (performance, security)
   - Python: Core logic (ecosystem, velocity)

---

## Final Recommendation

**Keep the hybrid architecture** ✅

```
┌─────────────┐
│   Svelte    │  ← Web skills, fast iteration
└──────┬──────┘
       │
┌──────▼──────┐
│ Rust/Tauri  │  ← Thin shell, security, small bundle
└──────┬──────┘
       │
┌──────▼──────┐
│   Python    │  ← Core logic, AI/ML ecosystem, free-threading
└─────────────┘
```

**Why this works**:
- ✅ Each layer uses the right tool
- ✅ Rust is minimal (~500 lines) - easy to maintain
- ✅ Python is core (~10k lines) - leverages ecosystem
- ✅ Svelte compiles away - no runtime overhead

**Packaging Strategy**:
1. **Now**: Require Python pre-install (small bundle)
2. **Q2 2024**: Add optional Python bundling
3. **Q3 2024**: Default to bundled Python

**Distribution**:
- **GitHub Releases**: Both small + full bundles
- **Homebrew**: `brew install sunwell-studio` (requires Python)
- **Direct Download**: Full bundle with Python included

---

## Next Steps

1. ✅ **Keep current architecture** (Rust + Python hybrid)
2. 📝 **Document Python requirement** in README
3. 🔨 **Add bundling script** for Phase 2 (optional Python bundle)
4. 📦 **Set up CI/CD** for multi-platform builds
5. 🚀 **Release small bundle first**, add full bundle later

---

## References

- [Tauri Resource Bundling](https://tauri.app/v1/guides/building/resources/)
- [PyInstaller Docs](https://pyinstaller.org/)
- [Python 3.14t Free-Threading](https://peps.python.org/pep-0703/)