// Real repository and two-browser collaboration check against the local demo.
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, sep } from 'node:path'
import puppeteer from 'puppeteer-core'

const base = process.env.REGIT_BASE_URL || 'http://127.0.0.1:8377'
assert(['127.0.0.1', 'localhost'].includes(new URL(base).hostname), 'Use a local demo endpoint.')
const chrome = [process.env.CHROME_BIN, process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].find(path => path && existsSync(path))
assert(chrome, 'Install Chrome or set CHROME_BIN to its executable path.')
const temporary = mkdtempSync(join(tmpdir(), 'regit-browser-'))
const initial = '# Browser finding\n\nInitial café evidence.'
writeFileSync(join(temporary, 'finding.md'), initial)
const browser = await puppeteer.launch({executablePath: chrome, headless: true,
  args: process.env.CI ? ['--no-sandbox'] : [], defaultViewport: {width: 1280, height: 950}})
const errors = []
const field = label => `[aria-label="${label}"]`
async function click(page, label) {
  const button = await page.waitForFunction(text => [...document.querySelectorAll('button')].find(button => button.textContent.trim() === text), {timeout: 10000}, label)
  await button.asElement().click()
}
async function value(page, label, expected) {
  await page.waitForFunction((selector, expected) => document.querySelector(selector)?.value === expected, {timeout: 10000}, field(label), expected)
}
async function pageIn(context, user) {
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.evaluateOnNewDocument(user => localStorage.setItem('regit_user', user), user)
  return page
}
try {
  const contextA = await browser.createBrowserContext()
  const a = await pageIn(contextA, 'userA')
  await a.goto(base, {waitUntil: 'domcontentloaded'})
  await a.locator(field('Repository name')).fill('Browser smoke ' + Date.now())
  let response = a.waitForResponse(response => response.url().endsWith('/api/repositories') && response.request().method() === 'POST')
  await click(a, 'Create repository')
  let result = await response; assert.equal(result.status(), 201)
  const rid = (await result.json()).id
  await a.locator(field('New folder name')).fill('sources/nested')
  response = a.waitForResponse(response => response.url().endsWith('/folders') && response.request().method() === 'POST')
  await click(a, 'Create folder'); result = await response; assert.equal(result.status(), 201)
  await click(a, 'sources/'); await click(a, 'nested/')
  const upload = await a.$(field('Upload repository files'))
  response = a.waitForResponse(response => response.url().endsWith('/files') && response.request().method() === 'POST')
  await upload.uploadFile(join(temporary, 'finding.md'))
  result = await response; assert.equal(result.status(), 201)
  await click(a, 'finding.md'); await value(a, 'Repository file contents', initial)
  await click(a, 'Live collaboration'); await value(a, 'Live research draft', initial)

  const contextB = await browser.createBrowserContext()
  const b = await pageIn(contextB, 'userB')
  await b.goto(base + '/#/repo/' + rid, {waitUntil: 'domcontentloaded'})
  await click(b, 'sources/'); await click(b, 'nested/'); await click(b, 'finding.md')
  await click(b, 'Live collaboration'); await value(b, 'Live research draft', initial)
  const first = '# Browser finding\n\nEvidence edited by A.'
  await a.locator(field('Live research draft')).fill(first)
  await value(b, 'Live research draft', first)
  const final = first + '\nclaim: Corroborated by B.'
  await b.locator(field('Live research draft')).fill(final)
  await value(a, 'Live research draft', final)
  await a.waitForFunction(() => document.body.innerText.includes('Peers: userB'))
  await click(a, 'Commit from live')
  await a.waitForFunction(() => document.body.innerText.includes('Saved commit'))
  await b.waitForFunction(() => document.body.innerText.includes('Saved commit'))
  response = a.waitForResponse(response => response.url().endsWith('/file/publish') && response.request().method() === 'POST')
  await click(a, 'Publish live file version'); result = await response; assert.equal(result.status(), 200)
  await a.locator(field('Live research draft')).fill('Discard this uncommitted draft.')
  await value(b, 'Live research draft', 'Discard this uncommitted draft.')
  a.once('dialog', dialog => dialog.accept())
  await click(a, 'Reset draft to latest commit')
  await value(a, 'Live research draft', final); await value(b, 'Live research draft', final)
  await click(a, 'File contents'); await value(a, 'Repository file contents', final)
  await a.reload({waitUntil: 'domcontentloaded'})
  await click(a, 'sources/'); await click(a, 'nested/'); await click(a, 'finding.md')
  await value(a, 'Repository file contents', final)
  await a.setViewport({width: 390, height: 844})
  assert(await a.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), 'Mobile repository overflows.')
  assert.deepEqual(errors, [])
  console.log('Browser smoke passed: repository, nested upload, bidirectional live edits, presence, commit, publication, reload and mobile layout.')
} finally {
  await browser.close()
  assert(resolve(temporary).startsWith(resolve(tmpdir()) + sep))
  rmSync(temporary, {recursive: true, force: true})
}
