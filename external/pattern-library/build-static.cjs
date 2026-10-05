// Use Sapper's existing exporter, not a second renderer or pattern engine.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const source = fs.readFileSync("src/routes/_index.js", "utf8");
const patterns = JSON.parse(source.match(/^const index = (.*);\s*export default index;/s)[1]);
const entries = ["/", ...patterns.map((pattern) => pattern.slug)].join(" ");
const cli = require.resolve("sapper/dist/cli.js");
// Make legal files available while crawling too: otherwise Sapper treats their
// links as missing dynamic routes and exports directories at the file names.
fs.copyFileSync("LICENSE.md", "static/LICENSE.md");
let notices = fs.readFileSync("UPSTREAM.md", "utf8") + "\n\n";
for (const name of ["svelte", "sapper", "@simonwep/pickr", "save-svg-as-png", "dayjs"]) {
  const folder = path.join("node_modules", name);
  const metadata = JSON.parse(fs.readFileSync(path.join(folder, "package.json"), "utf8"));
  const licenseFile = fs.readdirSync(folder).find((file) => /^licen[sc]e(\.|$)/i.test(file));
  if (!licenseFile) throw new Error("Missing third-party license: " + name);
  notices += name + " " + metadata.version + "\n" + fs.readFileSync(path.join(folder, licenseFile), "utf8") + "\n\n";
}
fs.writeFileSync("static/THIRD_PARTY_NOTICES.txt", notices);
execFileSync(process.execPath, [cli, "export", "--basepath", "patterns",
  "--entry", entries, "--concurrent", "4", "--timeout", "30000"], { stdio: "inherit" });
const output = "__sapper__/export/patterns";
for (const slug of ["", ...patterns.map((pattern) => pattern.slug)]) {
  const page = fs.readFileSync(path.join(output, slug, "index.html"), "utf8");
  if (!page.includes("小芒图案库") || /<title>[45]\d\d<\/title>/.test(page)
      || !page.includes("href=/patterns/")) {
    throw new Error("Invalid exported pattern page: " + (slug || "/"));
  }
}
console.log("Exported " + patterns.length + " patterns to " + output);
