import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join, relative, resolve } from 'node:path';

const repositoryRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const skillsRoot = join(repositoryRoot, 'skills');
const errors = [];
const discoveredNames = new Map();

function error(message) {
  errors.push(message);
}

function parseFrontmatter(filePath, content) {
  if (!content.startsWith('---\n')) {
    error(`${relative(repositoryRoot, filePath)}: missing YAML frontmatter`);
    return null;
  }

  const end = content.indexOf('\n---', 4);
  if (end === -1) {
    error(`${relative(repositoryRoot, filePath)}: unterminated YAML frontmatter`);
    return null;
  }

  const fields = new Map();
  for (const line of content.slice(4, end).split('\n')) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const match = line.match(/^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$/);
    if (!match) continue;
    fields.set(match[1], match[2].trim().replace(/^['"]|['"]$/g, ''));
  }
  return fields;
}

async function validateSkill(skillDirectory) {
  const skillName = skillDirectory.split('/').pop();
  const skillPath = join(skillsRoot, skillName, 'SKILL.md');
  let content;

  try {
    content = await readFile(skillPath, 'utf8');
  } catch {
    error(`${relative(repositoryRoot, skillPath)}: missing SKILL.md`);
    return;
  }

  const frontmatter = parseFrontmatter(skillPath, content);
  if (!frontmatter) return;

  const name = frontmatter.get('name');
  const description = frontmatter.get('description');
  const relativePath = relative(repositoryRoot, skillPath);

  if (!name) error(`${relativePath}: frontmatter requires name`);
  if (!description) error(`${relativePath}: frontmatter requires description`);
  if (name && name !== skillName) {
    error(`${relativePath}: name "${name}" must match directory "${skillName}"`);
  }
  if (name && (name.length > 64 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name))) {
    error(`${relativePath}: name must be lowercase alphanumeric words separated by single hyphens`);
  }
  if (description && description.length > 1024) {
    error(`${relativePath}: description must be at most 1024 characters`);
  }
  if (name) {
    if (discoveredNames.has(name)) {
      error(`${relativePath}: duplicate skill name; already used by ${discoveredNames.get(name)}`);
    } else {
      discoveredNames.set(name, relativePath);
    }
  }
}

let entries = [];
try {
  entries = await readdir(skillsRoot, { withFileTypes: true });
} catch {
  error('skills/: directory is missing');
}

for (const entry of entries) {
  if (!entry.isDirectory() || entry.name.startsWith('.')) continue;
  await validateSkill(entry.name);
}

if (errors.length) {
  console.error('Skill validation failed:');
  for (const message of errors) console.error(`- ${message}`);
  process.exit(1);
}

console.log(`Skill validation passed (${discoveredNames.size} skill${discoveredNames.size === 1 ? '' : 's'}).`);
