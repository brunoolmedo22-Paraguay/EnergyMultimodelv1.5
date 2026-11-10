// Real system Chromium; adds error telemetry without changing existing assertions.
const {chromium} = require('playwright');
const fs = require('fs');
const launch = chromium.launch.bind(chromium);
const events = [];
chromium.launch = async (options = {}) => {
  const browser = await launch({...options, executablePath: process.env.CHROMIUM_EXECUTABLE || '/usr/bin/chromium',
    args: [...(options.args || []), '--no-sandbox']});
  const attach = context => context.on('page', page => {
    page.on('pageerror', error => events.push({type: 'pageerror', url: page.url(), message: String(error)}));
    page.on('console', msg => {if (msg.type() === 'error') events.push({type: 'console.error', url: page.url(), message: msg.text()});});
  });
  browser.on('context', attach);
  const newContext = browser.newContext.bind(browser);
  browser.newContext = async (options = {}) => {
    if (process.env.E2E_DEVICE_SCALE) options = {...options, deviceScaleFactor:Number(process.env.E2E_DEVICE_SCALE)};
    const context = await newContext(options); attach(context); return context;
  };
  events.push({type: 'browser', version: browser.version(), executable: '/usr/bin/chromium'});
  return browser;
};
process.on('exit', () => {
  if (process.env.E2E_ERRORS_FILE) fs.writeFileSync(process.env.E2E_ERRORS_FILE, JSON.stringify(events, null, 2));
});
