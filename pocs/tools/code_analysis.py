"""
Code Analysis Tools for the Tech Writer multi-agent system.

This module provides tools for analyzing code structure and patterns.
"""

import os
import re
import json
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import ast
import importlib.util

from tools.file_tools import read_file, is_text_file

def detect_programming_languages(files: List[str]) -> Dict[str, int]:
    """Detect programming languages used in the codebase."""
    language_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "React/JavaScript",
        ".ts": "TypeScript",
        ".tsx": "React/TypeScript",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".less": "LESS",
        ".java": "Java",
        ".c": "C",
        ".cpp": "C++",
        ".cs": "C#",
        ".go": "Go",
        ".rb": "Ruby",
        ".php": "PHP",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".rs": "Rust",
        ".sh": "Shell",
        ".bat": "Batch",
        ".ps1": "PowerShell",
        ".sql": "SQL",
        ".r": "R",
        ".dart": "Dart",
        ".vue": "Vue",
        ".elm": "Elm",
        ".ex": "Elixir",
        ".exs": "Elixir",
        ".hs": "Haskell",
        ".fs": "F#",
        ".fsx": "F#",
        ".clj": "Clojure",
        ".scala": "Scala",
        ".pl": "Perl",
        ".pm": "Perl",
        ".lua": "Lua",
        ".groovy": "Groovy",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".toml": "TOML",
        ".xml": "XML",
        ".md": "Markdown",
        ".rst": "reStructuredText",
    }
    
    language_counts = {}
    
    for file_path in files:
        if not is_text_file(file_path):
            continue
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext in language_map:
            lang = language_map[ext]
            language_counts[lang] = language_counts.get(lang, 0) + 1
    
    return language_counts

def detect_frameworks(files: List[str]) -> Dict[str, List[str]]:
    """Detect frameworks and libraries used in the codebase."""
    framework_patterns = {
        "React": [r"import\s+.*?React", r"from\s+['\"]react['\"]", r"React\.", r"<React"],
        "Angular": [r"import\s+.*?from\s+['\"]@angular", r"NgModule", r"Component\("],
        "Vue": [r"import\s+.*?Vue", r"from\s+['\"]vue['\"]", r"new\s+Vue", r"createApp"],
        "Express": [r"import\s+.*?express", r"require\(['\"]express['\"]", r"app\.use", r"app\.get"],
        "Django": [r"from\s+django", r"urls\.py", r"views\.py", r"models\.py"],
        "Flask": [r"from\s+flask", r"Flask\(", r"app\.route"],
        "Spring": [r"@SpringBootApplication", r"@RestController", r"@Autowired"],
        "Laravel": [r"use\s+Illuminate", r"extends\s+Controller", r"Schema::create"],
        "Ruby on Rails": [r"class\s+.*?<\s+ApplicationController", r"ActiveRecord", r"has_many"],
        "Next.js": [r"import\s+.*?from\s+['\"]next", r"getStaticProps", r"getServerSideProps"],
        "NestJS": [r"import\s+.*?from\s+['\"]@nestjs", r"@Module", r"@Controller"],
        "TensorFlow": [r"import\s+.*?tensorflow", r"import\s+.*?tf", r"tf\.", r"tensorflow\."],
        "PyTorch": [r"import\s+torch", r"torch\.", r"nn\.Module"],
        "Pandas": [r"import\s+pandas", r"pd\.", r"DataFrame"],
        "NumPy": [r"import\s+numpy", r"np\.", r"numpy\."],
        "Scikit-learn": [r"import\s+sklearn", r"from\s+sklearn"],
        "Redux": [r"import\s+.*?redux", r"createStore", r"useSelector", r"useDispatch"],
        "GraphQL": [r"import\s+.*?graphql", r"gql`", r"type\s+Query", r"type\s+Mutation"],
        "Apollo": [r"import\s+.*?apollo", r"ApolloClient", r"useQuery", r"useMutation"],
        "Webpack": [r"webpack\.config", r"module\.exports", r"entry:", r"output:"],
        "Jest": [r"import\s+.*?jest", r"describe\(", r"test\(", r"it\(", r"expect\("],
        "Mocha": [r"import\s+.*?mocha", r"describe\(", r"it\("],
        "Chai": [r"import\s+.*?chai", r"expect\(", r"assert\."],
        "Bootstrap": [r"import\s+.*?bootstrap", r"class=\"btn", r"class=\"container"],
        "Tailwind": [r"tailwind\.config", r"class=\".*?bg-", r"class=\".*?text-", r"class=\".*?flex"],
        "Material-UI": [r"import\s+.*?@material-ui", r"import\s+.*?@mui", r"<Button", r"<AppBar"],
        "Chakra UI": [r"import\s+.*?@chakra-ui", r"<ChakraProvider", r"<Box", r"<Flex"],
        "Styled Components": [r"import\s+.*?styled-components", r"styled\.", r"css`"],
        "Emotion": [r"import\s+.*?@emotion", r"css`", r"styled\("],
        "Axios": [r"import\s+.*?axios", r"axios\.", r"axios\("],
        "Fetch API": [r"fetch\(", r"\.then\(", r"\.json\("],
        "Socket.io": [r"import\s+.*?socket\.io", r"io\(", r"socket\.on"],
        "Sequelize": [r"import\s+.*?sequelize", r"Model\.init", r"DataTypes"],
        "TypeORM": [r"import\s+.*?typeorm", r"@Entity", r"@Column"],
        "Prisma": [r"import\s+.*?@prisma", r"prisma\.", r"schema\.prisma"],
        "Mongoose": [r"import\s+.*?mongoose", r"mongoose\.", r"Schema\("],
        "SQLAlchemy": [r"import\s+.*?sqlalchemy", r"Column\(", r"relationship\("],
        "Drizzle": [r"import\s+.*?drizzle", r"drizzle\.", r"createInsertSchema"],
    }
    
    frameworks = {}
    
    for file_path in files:
        if not is_text_file(file_path):
            continue
            
        content = read_file(file_path)
        if isinstance(content, str) and not content.startswith("Error") and not content.startswith("[Binary"):
            for framework, patterns in framework_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, content):
                        if framework not in frameworks:
                            frameworks[framework] = []
                        if file_path not in frameworks[framework]:
                            frameworks[framework].append(file_path)
    
    return frameworks

def extract_python_imports(file_path: str) -> List[str]:
    """Extract import statements from a Python file."""
    content = read_file(file_path)
    if not isinstance(content, str) or content.startswith("Error") or content.startswith("[Binary"):
        return []
    
    imports = []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    if module:
                        imports.append(f"{module}.{name.name}")
                    else:
                        imports.append(name.name)
    except Exception:
        # Fall back to regex for syntax errors
        import_pattern = r"^\s*(import|from)\s+([^\s;]+)"
        for line in content.split("\n"):
            match = re.match(import_pattern, line)
            if match:
                imports.append(match.group(2))
    
    return imports

def extract_js_imports(file_path: str) -> List[str]:
    """Extract import statements from a JavaScript/TypeScript file."""
    content = read_file(file_path)
    if not isinstance(content, str) or content.startswith("Error") or content.startswith("[Binary"):
        return []
    
    imports = []
    
    # ES6 imports
    es6_pattern = r"import\s+(?:(?:{[^}]+}|\*\s+as\s+[^,]+|[^,{]+)(?:,\s*(?:{[^}]+}|\*\s+as\s+[^,]+|[^,{]+))*\s+from\s+)?['\"]([^'\"]+)['\"]"
    for match in re.finditer(es6_pattern, content):
        imports.append(match.group(1))
    
    # CommonJS require
    cjs_pattern = r"(?:const|let|var)\s+(?:{[^}]+}|[^=]+)\s*=\s*require\(['\"]([^'\"]+)['\"]\)"
    for match in re.finditer(cjs_pattern, content):
        imports.append(match.group(1))
    
    return imports

def analyze_dependencies(files: List[str]) -> Dict[str, Any]:
    """Analyze dependencies in the codebase."""
    dependencies = {
        "python": set(),
        "javascript": set(),
        "typescript": set(),
        "other": set()
    }
    
    package_files = {
        "python": [],
        "javascript": [],
        "other": []
    }
    
    for file_path in files:
        if not is_text_file(file_path):
            continue
            
        filename = os.path.basename(file_path)
        if filename == "requirements.txt":
            package_files["python"].append(file_path)
        elif filename == "package.json":
            package_files["javascript"].append(file_path)
        elif filename == "Pipfile":
            package_files["python"].append(file_path)
        elif filename == "pyproject.toml":
            package_files["python"].append(file_path)
        elif filename.endswith(".csproj") or filename.endswith(".fsproj"):
            package_files["other"].append(file_path)
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".py"]:
            for imp in extract_python_imports(file_path):
                if "." not in imp or imp.split(".")[0] not in ["os", "sys", "re", "json", "time", "datetime"]:
                    dependencies["python"].add(imp.split(".")[0])
        elif ext in [".js", ".jsx"]:
            for imp in extract_js_imports(file_path):
                if not imp.startswith(".") and not imp.startswith("/"):
                    dependencies["javascript"].add(imp.split("/")[0])
        elif ext in [".ts", ".tsx"]:
            for imp in extract_js_imports(file_path):
                if not imp.startswith(".") and not imp.startswith("/"):
                    dependencies["typescript"].add(imp.split("/")[0])
    
    # Parse package files
    for lang, files in package_files.items():
        for file_path in files:
            content = read_file(file_path)
            if not isinstance(content, str) or content.startswith("Error"):
                continue
                
            if os.path.basename(file_path) == "requirements.txt":
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Remove version specifiers
                        package = re.split(r'[=<>~]', line)[0].strip()
                        dependencies["python"].add(package)
            elif os.path.basename(file_path) == "package.json":
                try:
                    data = json.loads(content)
                    for section in ["dependencies", "devDependencies"]:
                        if section in data:
                            for package in data[section]:
                                dependencies["javascript"].add(package)
                except json.JSONDecodeError:
                    pass
    
    return {
        "python": sorted(list(dependencies["python"])),
        "javascript": sorted(list(dependencies["javascript"])),
        "typescript": sorted(list(dependencies["typescript"])),
        "other": sorted(list(dependencies["other"]))
    }

def detect_database_usage(files: List[str]) -> Dict[str, List[str]]:
    """Detect database technologies used in the codebase."""
    db_patterns = {
        "PostgreSQL": [r"postgresql", r"postgres", r"psycopg2", r"pg\.", r"pgAdmin"],
        "MySQL": [r"mysql", r"MariaDB", r"InnoDB"],
        "SQLite": [r"sqlite", r"sqlite3"],
        "MongoDB": [r"mongodb", r"mongoose", r"MongoClient"],
        "Redis": [r"redis", r"RedisClient"],
        "DynamoDB": [r"dynamodb", r"DynamoDBClient"],
        "Firestore": [r"firestore", r"Firestore"],
        "Cassandra": [r"cassandra", r"CassandraClient"],
        "Neo4j": [r"neo4j", r"GraphDatabase"],
        "Elasticsearch": [r"elasticsearch", r"Elasticsearch"],
        "Oracle": [r"oracle", r"oracledb", r"cx_Oracle"],
        "SQL Server": [r"sqlserver", r"mssql", r"pyodbc", r"tedious"],
        "Supabase": [r"supabase", r"createClient"],
        "Prisma": [r"prisma", r"PrismaClient"],
        "Drizzle": [r"drizzle", r"DrizzleClient"],
    }
    
    databases = {}
    
    for file_path in files:
        if not is_text_file(file_path):
            continue
            
        content = read_file(file_path)
        if isinstance(content, str) and not content.startswith("Error") and not content.startswith("[Binary"):
            for db, patterns in db_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        if db not in databases:
                            databases[db] = []
                        if file_path not in databases[db]:
                            databases[db].append(file_path)
    
    return databases

def extract_api_endpoints(files: List[str]) -> List[Dict[str, Any]]:
    """Extract API endpoints from the codebase."""
    endpoints = []
    
    # Express.js patterns
    express_patterns = [
        r"(app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
        r"(app|router)\.(route)\s*\(\s*['\"]([^'\"]+)['\"].*?\.(get|post|put|delete|patch)"
    ]
    
    # Flask patterns
    flask_patterns = [
        r"@(app|blueprint)\.route\s*\(\s*['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?"
    ]
    
    # Django patterns
    django_patterns = [
        r"path\s*\(\s*['\"]([^'\"]+)['\"](?:,\s*([^,]+))?"
    ]
    
    # FastAPI patterns
    fastapi_patterns = [
        r"@(app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]"
    ]
    
    for file_path in files:
        if not is_text_file(file_path):
            continue
            
        content = read_file(file_path)
        if not isinstance(content, str) or content.startswith("Error") or content.startswith("[Binary"):
            continue
            
        # Check Express.js patterns
        for pattern in express_patterns:
            for match in re.finditer(pattern, content):
                if len(match.groups()) == 3:
                    app, method, path = match.groups()
                    endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "framework": "Express.js",
                        "file": file_path
                    })
                elif len(match.groups()) == 4:
                    app, route, path, method = match.groups()
                    endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "framework": "Express.js",
                        "file": file_path
                    })
        
        # Check Flask patterns
        for pattern in flask_patterns:
            for match in re.finditer(pattern, content):
                app, path, methods = match.groups() if len(match.groups()) == 3 else (match.group(1), match.group(2), "GET")
                if methods:
                    methods = [m.strip().strip("'\"") for m in methods.split(",")]
                else:
                    methods = ["GET"]
                
                for method in methods:
                    endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "framework": "Flask",
                        "file": file_path
                    })
        
        # Check Django patterns
        for pattern in django_patterns:
            for match in re.finditer(pattern, content):
                path, view = match.groups()
                endpoints.append({
                    "path": path,
                    "method": "ANY",  # Django doesn't specify methods in URLs
                    "framework": "Django",
                    "file": file_path
                })
        
        # Check FastAPI patterns
        for pattern in fastapi_patterns:
            for match in re.finditer(pattern, content):
                app, method, path = match.groups()
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "framework": "FastAPI",
                    "file": file_path
                })
    
    return endpoints

def analyze_code_structure(files: List[str]) -> Dict[str, Any]:
    """Analyze the structure of the code (classes, functions, etc.)."""
    structure = {
        "classes": [],
        "functions": [],
        "imports": [],
        "exports": []
    }
    
    for file_path in files:
        if not is_text_file(file_path):
            continue
            
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".py":
            try:
                content = read_file(file_path)
                if not isinstance(content, str) or content.startswith("Error") or content.startswith("[Binary"):
                    continue
                    
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        structure["classes"].append({
                            "name": node.name,
                            "file": file_path,
                            "line": node.lineno,
                            "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                        })
                    elif isinstance(node, ast.FunctionDef) and not isinstance(node.parent, ast.ClassDef):
                        structure["functions"].append({
                            "name": node.name,
                            "file": file_path,
                            "line": node.lineno
                        })
            except Exception:
                pass
        
        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            content = read_file(file_path)
            if not isinstance(content, str) or content.startswith("Error") or content.startswith("[Binary"):
                continue
                
            # Extract class definitions
            class_pattern = r"class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{"
            for match in re.finditer(class_pattern, content):
                class_name = match.group(1)
                parent_class = match.group(2)
                
                # Find methods within the class
                class_content = content[match.end():]
                method_pattern = r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*{" 
                methods = [m.group(1) for m in re.finditer(method_pattern, class_content)]
                
                structure["classes"].append({
                    "name": class_name,
                    "file": file_path,
                    "extends": parent_class,
                    "methods": methods
                })
            
            # Extract function definitions
            function_pattern = r"(?:function|const|let|var)\s+(\w+)\s*=?\s*(?:function)?\s*\("
            for match in re.finditer(function_pattern, content):
                structure["functions"].append({
                    "name": match.group(1),
                    "file": file_path
                })
            
            # Extract exports
            export_pattern = r"export\s+(?:default\s+)?(?:function|class|const|let|var)?\s*(\w+)"
            for match in re.finditer(export_pattern, content):
                structure["exports"].append({
                    "name": match.group(1),
                    "file": file_path
                })
    
    return structure
