"use strict";

const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT_FILES = new Set(["package.json", "README.md"]);
const PACKAGED_DIRS = ["media/", "src/"];
const VENDORED_SERVICE_DIR = "python-service";
const VENDORED_SERVICE_ROOT_FILES = new Set(["README.md", "pyproject.toml"]);
const VENDORED_SERVICE_DIRS = ["biocursor_service/", "dogma_service/"];

function escapeXml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function toPosixPath(filePath) {
  return filePath.split(path.sep).join("/");
}

function shouldPackageFile(relativePath) {
  if (ROOT_FILES.has(relativePath)) return true;
  if (relativePath.startsWith(`${VENDORED_SERVICE_DIR}/`)) return shouldPackageVendoredServiceFile(relativePath.slice(VENDORED_SERVICE_DIR.length + 1));
  return PACKAGED_DIRS.some((dir) => relativePath.startsWith(dir));
}

function shouldPackageVendoredServiceFile(relativePath) {
  if (VENDORED_SERVICE_ROOT_FILES.has(relativePath)) return true;
  if (relativePath.includes("__pycache__/")) return false;
  if (relativePath.endsWith(".pyc")) return false;
  if (relativePath.startsWith("tests/")) return false;
  if (!relativePath.endsWith(".py")) return false;
  return VENDORED_SERVICE_DIRS.some((dir) => relativePath.startsWith(dir));
}

function walkFiles(rootDir, currentDir = rootDir) {
  const entries = fs.readdirSync(currentDir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(currentDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(rootDir, fullPath));
      continue;
    }

    if (entry.isFile()) {
      files.push(toPosixPath(path.relative(rootDir, fullPath)));
    }
  }

  return files;
}

function listPackageFiles(sourceRoot) {
  const extensionFiles = walkFiles(sourceRoot)
    .filter(shouldPackageFile)
    .sort((a, b) => a.localeCompare(b));
  const serviceRoot = resolveVendoredServiceRoot(sourceRoot);
  const serviceFiles = serviceRoot
    ? walkFiles(serviceRoot)
        .filter(shouldPackageVendoredServiceFile)
        .map((filePath) => `${VENDORED_SERVICE_DIR}/${filePath}`)
    : [];
  return [...extensionFiles, ...serviceFiles].sort((a, b) => a.localeCompare(b));
}

function buildContentTypesXml() {
  return [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
    '  <Default Extension="json" ContentType="application/json"/>',
    '  <Default Extension="js" ContentType="application/javascript"/>',
    '  <Default Extension="md" ContentType="text/markdown"/>',
    '  <Default Extension="py" ContentType="text/x-python"/>',
    '  <Default Extension="svg" ContentType="image/svg+xml"/>',
    '  <Default Extension="toml" ContentType="text/plain"/>',
    '  <Default Extension="vsixmanifest" ContentType="text/xml"/>',
    '  <Default Extension="xml" ContentType="text/xml"/>',
    "</Types>",
    ""
  ].join("\n");
}

function buildVsixManifest(packageJson) {
  const engine = packageJson.engines && packageJson.engines.vscode ? packageJson.engines.vscode : "*";
  const categories = Array.isArray(packageJson.categories) ? packageJson.categories.join(",") : "Other";

  return [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">',
    "  <Metadata>",
    `    <Identity Language="en-US" Id="${escapeXml(packageJson.name)}" Version="${escapeXml(packageJson.version)}" Publisher="${escapeXml(packageJson.publisher)}"/>`,
    `    <DisplayName>${escapeXml(packageJson.displayName || packageJson.name)}</DisplayName>`,
    `    <Description xml:space="preserve">${escapeXml(packageJson.description || "")}</Description>`,
    "    <Tags>dogma,bioinformatics,genomics,workflow,nextflow,vscode,cursor</Tags>",
    `    <Categories>${escapeXml(categories)}</Categories>`,
    "    <GalleryFlags>Public</GalleryFlags>",
    "    <Properties>",
    `      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="${escapeXml(engine)}"/>`,
    "    </Properties>",
    "  </Metadata>",
    "  <Installation>",
    '    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>',
    "  </Installation>",
    "  <Dependencies/>",
    "  <Assets>",
    '    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>',
    '    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true"/>',
    "  </Assets>",
    "</PackageManifest>",
    ""
  ].join("\n");
}

function resolveVendoredServiceRoot(sourceRoot) {
  const candidates = [
    path.resolve(sourceRoot, "../dogma-local-service"),
    path.resolve(sourceRoot, "../biocursor-local-service")
  ];
  return candidates.find((candidate) => fs.existsSync(path.join(candidate, "dogma_service", "__main__.py"))) || null;
}

function copyFileIntoExtension(sourceRoot, stagingRoot, relativePath) {
  const serviceRoot = relativePath.startsWith(`${VENDORED_SERVICE_DIR}/`) ? resolveVendoredServiceRoot(sourceRoot) : null;
  const source = serviceRoot
    ? path.join(serviceRoot, relativePath.slice(VENDORED_SERVICE_DIR.length + 1))
    : path.join(sourceRoot, relativePath);
  const destination = path.join(stagingRoot, "extension", relativePath);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.copyFileSync(source, destination);
}

function stageVsix(sourceRoot, stagingRoot, packageFiles, packageJson) {
  fs.rmSync(stagingRoot, { recursive: true, force: true });
  fs.mkdirSync(stagingRoot, { recursive: true });

  fs.writeFileSync(path.join(stagingRoot, "[Content_Types].xml"), buildContentTypesXml(), "utf8");
  fs.writeFileSync(path.join(stagingRoot, "extension.vsixmanifest"), buildVsixManifest(packageJson), "utf8");

  packageFiles.forEach((relativePath) => copyFileIntoExtension(sourceRoot, stagingRoot, relativePath));
}

function createVsix(options = {}) {
  const sourceRoot = options.sourceRoot || path.resolve(__dirname, "..");
  const packageJsonPath = path.join(sourceRoot, "package.json");
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
  const outputPath =
    options.outputPath || path.resolve(sourceRoot, "..", `${packageJson.name}-${packageJson.version}.vsix`);
  const stagingRoot =
    options.stagingRoot || path.resolve(sourceRoot, "..", ".dogma-vsix-staging", packageJson.name);
  const packageFiles = listPackageFiles(sourceRoot);

  stageVsix(sourceRoot, stagingRoot, packageFiles, packageJson);
  fs.rmSync(outputPath, { force: true });

  try {
    childProcess.execFileSync("zip", ["-qr", outputPath, "."], { cwd: stagingRoot });
  } catch (error) {
    if (error.code === "ENOENT") {
      throw new Error("The system zip command is required to build a VSIX package.");
    }
    throw error;
  } finally {
    fs.rmSync(path.dirname(stagingRoot), { recursive: true, force: true });
  }

  return {
    outputPath,
    files: packageFiles
  };
}

if (require.main === module) {
  const outputArg = process.argv[2] ? path.resolve(process.cwd(), process.argv[2]) : undefined;
  const result = createVsix({ outputPath: outputArg });
  console.log(`created ${result.outputPath}`);
  console.log(`packaged ${result.files.length} extension files`);
}

module.exports = {
  buildContentTypesXml,
  buildVsixManifest,
  createVsix,
  escapeXml,
  listPackageFiles,
  resolveVendoredServiceRoot,
  shouldPackageVendoredServiceFile,
  shouldPackageFile
};
