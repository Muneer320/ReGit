// Headless smoke test of the full demo flow against dev server + live backend.
import puppeteer from 'puppeteer-core'

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const BASE = 'http://localhost:5173'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function text(page, sel) {
  return page.$eval(sel, (el) => el.textContent).catch(() => null)
}
async function clickByText(page, selector, label) {
  const handles = await page.$$(selector)
  for (const h of handles) {
    const t = await h.evaluate((el) => el.textContent.trim())
    if (t.includes(label)) {
      await h.click()
      return true
    }
  }
  return false
}

async function waitForAny(page, sels, timeoutMs = 9000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    for (const s of sels) {
      if (await page.$(s)) return s
    }
    await sleep(200)
  }
  return null
}

const run = async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--window-size=1500,950'],
    defaultViewport: { width: 1500, height: 950 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(`PAGEERROR: ${e.message}`))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`CONSOLE: ${m.text()}`)
  })

  console.log('— open workspace')
  await page.goto(BASE + '/#/', { waitUntil: 'networkidle0' })
  await sleep(800)
  console.log('  title:', await page.title())
  const body = await text(page, '.main')
  console.log('  has workspace heading:', body?.includes('Workspace'))

  console.log('— load demo data')
  const seeded = await clickByText(page, 'button', 'Load demo data')
  console.log('  clicked:', seeded)
  await sleep(2500)
  const rows = await page.$$eval('.artifact-table tbody tr', (tr) => tr.map((r) => r.textContent)).catch(() => [])
  console.log('  artifact rows:', rows.length)

  if (rows.length === 0) throw new Error('no artifacts after seeding')

  // Open the lr-stability artifact (merge scene)
  console.log('— open lr-stability.md')
  const lrRow = rows.find((r) => r.includes('lr-stability'))
  console.log('  found row:', !!lrRow)
  await page.evaluate((txt) => {
    const trs = [...document.querySelectorAll('.artifact-table tbody tr')]
    trs.find((t) => t.textContent.includes(txt)).click()
  }, 'lr-stability')
  await sleep(1200)
  console.log('  overview h1:', await text(page, 'h1'))

  console.log('— history')
  await clickByText(page, '.nav-item', 'History')
  await sleep(1000)
  const commits = await page.$$eval('.commit-item', (cs) => cs.map((c) => c.querySelector('.commit-msg')?.textContent))
  console.log('  commits:', commits.length, JSON.stringify(commits.slice(0, 3)))

  console.log('— semantic diff')
  await clickByText(page, '.nav-item', 'Diff')
  await sleep(1800)
  const stats = await text(page, '.diff-stats').catch(() => null)
  console.log('  diff stats:', stats)
  const changeRows = await page.$$eval('.change-row', (rs) => rs.map((r) => r.className.match(/row-(\w+)/)?.[1]))
  console.log('  change rows:', JSON.stringify(changeRows))
  await page.screenshot({ path: '/tmp/regit-diff.png' })

  console.log('— merge scene')
  await clickByText(page, '.nav-item', 'Merge')
  await sleep(900)
  const attempt = await clickByText(page, 'button', 'Attempt merge')
  console.log('  attempted:', attempt)
  const which = await waitForAny(page, ['.conflict-banner', '.merge-success', '.toast.error'])
  console.log('  merge outcome:', which)
  const banner = await text(page, '.conflict-banner').catch(() => null)
  console.log('  conflict banner:', banner?.slice(0, 60))
  const cards = await page.$$('.conflict-card')
  console.log('  conflict cards:', cards.length)
  if (!which) await page.screenshot({ path: '/tmp/regit-merge-stuck.png' })
  await page.screenshot({ path: '/tmp/regit-conflict.png' })

  if (cards.length > 0) {
    console.log('— accept theirs on card 1')
    await clickByText(page, '.conflict-card button', 'Accept Theirs')
    await sleep(400)
    console.log('— commit resolution')
    const commitBtn = await clickByText(page, 'button', 'Commit merge')
    console.log('  clicked commit:', commitBtn)
    const ok = await waitForAny(page, ['.merge-success', '.toast.error'])
    console.log('  resolution outcome:', ok)
    const success = await text(page, '.merge-success').catch(() => null)
    console.log('  success panel:', success ? success.replace(/\s+/g, ' ').slice(0, 140) : null)
    await page.screenshot({ path: '/tmp/regit-success.png' })

    if (success) {
      console.log('— view history after merge (2 parents expected)')
      await clickByText(page, '.merge-success button', 'View history')
      await waitForAny(page, ['.commit-item'])
      await sleep(800)
      const commits2 = await page.$$eval('.commit-item', (cs) =>
        cs.map((c) => ({ msg: c.querySelector('.commit-msg')?.textContent, merge: !!c.querySelector('.commit-dot.merge') })),
      )
      console.log('  top commits:', JSON.stringify(commits2.slice(0, 3), null, 1))
    }
  }

  console.log('— search')
  await page.goto(BASE + '/#/search', { waitUntil: 'networkidle0' })
  await sleep(600)
  await page.type('.search-input', 'gradient descent instability')
  await page.keyboard.press('Enter')
  await sleep(2000)
  const results = await page.$$eval('.result-card', (rs) => rs.map((r) => ({
    title: r.querySelector('b')?.textContent,
    citation: r.querySelector('.citation-line')?.textContent?.replace(/\s+/g, ' ').trim().slice(0, 130),
  })))
  console.log('  results:', results.length)
  results.slice(0, 3).forEach((r) => console.log('   •', r.title, '|', r.citation))
  await page.screenshot({ path: '/tmp/regit-search.png' })

  console.log('\nERRORS:', errors.length === 0 ? 'none' : '')
  errors.slice(0, 12).forEach((e) => console.log(' ', e.slice(0, 220)))
  await browser.close()
}

run().catch((e) => {
  console.error('SMOKE FAIL:', e.message)
  process.exit(1)
})
