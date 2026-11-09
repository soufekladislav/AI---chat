(() => {
  const url = 'https://chat.freshcrackers.cz/';
  const text = 'Vyzkoušej Fresh AI Chat – vytvoř si vlastního AI parťáka: ' + url;
  const status = document.getElementById('shareStatus');
  const setStatus = message => { if (status) status.textContent=message; };
  const shareUrl = {
    facebook: 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(url),
    whatsapp: 'https://api.whatsapp.com/send?text=' + encodeURIComponent(text),
    x: 'https://twitter.com/intent/tweet?text=' + encodeURIComponent('Vyzkoušej Fresh AI Chat – vytvoř si vlastního AI parťáka!') + '&url=' + encodeURIComponent(url),
    linkedin: 'https://www.linkedin.com/sharing/share-offsite/?url=' + encodeURIComponent(url)
  };
  async function copyLink() {
    try { await navigator.clipboard.writeText(text); setStatus('Odkaz zkopírován. V TikToku vlož odkaz do vlastního příspěvku.'); }
    catch (_) { setStatus('Zkopíruj prosím adresu ' + url + ' a vlož ji do TikToku.'); }
  }
  document.querySelectorAll('[data-share]').forEach(element => {
    const type = element.dataset.share;
    if (shareUrl[type]) { element.href=shareUrl[type]; element.target='_blank'; element.rel='noopener noreferrer'; return; }
    element.addEventListener('click', async event => {
      event.preventDefault();
      if (type==='native' && navigator.share) {
        try { await navigator.share({title:'Fresh AI Chat',text:'Vyzkoušej Fresh AI Chat',url}); setStatus('Odkaz předán nabídce sdílení.'); }
        catch (error) { if(error.name!=='AbortError') await copyLink(); }
      } else { await copyLink(); }
    });
  });
})();
