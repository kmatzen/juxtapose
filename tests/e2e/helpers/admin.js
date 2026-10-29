// The authenticated admin session comes from tests/e2e/auth.setup.js, so these specs
// land on /admin directly instead of spending the IP-keyed 10/hour login budget.

const pageOverflow = (page) => page.evaluate(() => {
  const scroll = document.querySelector('.table-scroll');
  return {
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    gridScrollable: !!scroll && scroll.scrollWidth > scroll.clientWidth,
  };
});

module.exports = { pageOverflow };
