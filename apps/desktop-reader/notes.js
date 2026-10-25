/* Plain textareas preserve native Chinese IME composition and candidate selection. */
let textMode = false, noteToken = '', notes = [];
const noteSaves = new Map();
const draftPrefix = 'chinese-book.pending.'+book.id+'.';
$('reveal').addEventListener('click', async () => {
  $('reveal').disabled = true;
  try {
    await notesReady;
    await Promise.all(notes.filter(n => noteSaves.has(n.id)).map(saveNote));
    await saveQueue;
    const response = await fetch('/api/reveal', {method:'POST',
      headers:{'Content-Type':'application/json','X-Reader-Token':noteToken},body:'{}'});
    if (!response.ok) throw new Error('Could not open the PDF location.');
  } catch (error) { $('notice').textContent = error.message; }
  finally { $('reveal').disabled = false; }
});
const notesReady = fetch('/api/notes').then(r => {
  if (!r.ok) throw new Error('Cannot load saved textboxes');
  return r.json();
}).then(data => {
  noteToken = data.token; notes = data.notes;
  notes.forEach(renderNote);
}).catch(error => { $('notice').textContent = error.message; });
function setTextMode(enabled) {
  textMode = enabled;
  viewer.classList.toggle('text-mode', enabled);
}
function renderNote(note) {
  const index = book.pages.findIndex(p => p.page === note.page), sheet = sheets[index];
  if (!sheet) return;
  const field = document.createElement('textarea');
  field.className = 'note'; field.dataset.note = note.id;
  field.value = note.text; field.lang = 'zh-CN'; field.spellcheck = false;
  field.setAttribute('aria-label','PDF textbox');
  Object.assign(field.style, {left:100*note.x+'%',top:100*note.y+'%',width:100*note.w+'%',
    height:100*note.h+'%',fontSize:`calc(var(--page-width) * ${note.font_size/book.pages[index].width})`});
  // Inline text has native hit boxes for each wrapped line, unlike a textarea.
  const preview = document.createElement('div'); preview.className = 'note-preview';
  const readout = document.createElement('span'); readout.textContent = note.text;
  preview.append(readout);
  for (const key of ['left','top','width','fontSize']) preview.style[key] = field.style[key];
  let composing = false, removed = false, drag = null, suppressClick = false;
  function discard() {
    if (removed) return;
    removed = true;
    clearTimeout(noteSaves.get(note.id)); noteSaves.delete(note.id);
    note.text = '';
    notes = notes.filter(n => n.id !== note.id);
    field.remove();
    preview.remove();
    saveNote(note);
  }
  function finishEditing() {
    if (composing || removed || drag) return;
    if (!field.value.trim()) discard();
    else { update(); saveNote(note); }
  }
  function update() {
    if (removed || drag) return;
    note.text = field.value;
    readout.textContent = field.value;
    field.style.height = '1px';
    const height = Math.max(field.scrollHeight+2, parseFloat(getComputedStyle(field).fontSize)*1.5);
    note.h = Math.min(1-note.y, height/sheet.clientHeight);
    field.style.height = 100*note.h+'%';
    if (!composing) scheduleNoteSave(note);
  }
  field.addEventListener('compositionstart', () => { composing = true; clearTimeout(noteSaves.get(note.id)); });
  field.addEventListener('compositionend', () => {
    composing = false;
    if (document.activeElement === field) update(); else finishEditing();
  });
  field.addEventListener('input', update);
  field.addEventListener('blur', finishEditing);
  field.addEventListener('keydown', event => {
    // Enter belongs to the IME while its candidate window is active.
    if (event.isComposing || composing || event.keyCode === 229) return;
    if (event.key === 'Escape' || ((event.ctrlKey || event.metaKey) && event.key === 'Enter')) {
      event.preventDefault(); field.blur(); viewer.focus({preventScroll:true});
    }
    event.stopPropagation();
  });
  function beginPointer(event) {
    if (event.button !== 0) return;
    if (event.altKey) { event.preventDefault(); event.stopPropagation(); return; }
    if (!event.ctrlKey) return;
    event.preventDefault(); event.stopPropagation(); finishPinch();
    clearTimeout(noteSaves.get(note.id)); noteSaves.delete(note.id);
    const box = sheet.getBoundingClientRect();
    drag = {id:event.pointerId, x:event.clientX, y:event.clientY,
      left:note.x, top:note.y, width:box.width, height:box.height, moved:false};
    field.classList.add('dragging');
    field.setPointerCapture(event.pointerId);
  }
  field.addEventListener('pointerdown', beginPointer);
  preview.addEventListener('pointerdown', beginPointer);
  field.addEventListener('pointermove', event => {
    if (!drag || event.pointerId !== drag.id) return;
    event.preventDefault(); event.stopPropagation();
    const dx = event.clientX-drag.x, dy = event.clientY-drag.y;
    if (!drag.moved && Math.hypot(dx,dy)<3) return;
    drag.moved = true;
    note.x = Math.max(0, Math.min(1-note.w, drag.left+dx/drag.width));
    note.y = Math.max(0, Math.min(1-note.h, drag.top+dy/drag.height));
    field.style.left = 100*note.x+'%'; field.style.top = 100*note.y+'%';
    preview.style.left = field.style.left; preview.style.top = field.style.top;
  });
  function endDrag(event) {
    if (!drag || event.pointerId !== drag.id) return;
    const gesture = drag; drag = null;
    field.classList.remove('dragging');
    if (field.hasPointerCapture(gesture.id)) field.releasePointerCapture(gesture.id);
    if (gesture.moved) {
      suppressClick = true;
      setTimeout(() => { suppressClick = false; }, 0);
      saveNote(note);
    }
  }
  field.addEventListener('pointerup', endDrag);
  field.addEventListener('pointercancel', endDrag);
  field.addEventListener('lostpointercapture', endDrag);
  function clickNote(event) {
    event.stopPropagation();
    if (suppressClick) { suppressClick = false; event.preventDefault(); return; }
    if (removed) return;
    if (event.altKey) { event.preventDefault(); discard(); return; }
    if (event.currentTarget === preview) {
      const caret = document.caretRangeFromPoint(event.clientX,event.clientY);
      const offset = caret?.startContainer === readout.firstChild ? caret.startOffset : field.value.length;
      field.focus({preventScroll:true});
      field.setSelectionRange(offset,offset);
    }
  }
  field.addEventListener('click', clickNote);
  preview.addEventListener('click', clickNote);
  sheet.append(field,preview);
  return field;
}
function scheduleNoteSave(note) {
  clearTimeout(noteSaves.get(note.id));
  noteSaves.set(note.id, setTimeout(() => saveNote(note), 700));
}
// Serialize writes, so an older request cannot replace a newer edit.
let saveQueue = Promise.resolve();
function saveNote(note) {
  clearTimeout(noteSaves.get(note.id)); noteSaves.delete(note.id);
  const snapshot = JSON.stringify(note);
  // Retain pending edits through a window close or interrupted disk write.
  try { localStorage.setItem(draftPrefix+note.id, snapshot); } catch {}
  saveQueue = saveQueue.catch(() => {}).then(async () => {
    const response = await fetch('/api/notes', {method:'POST',keepalive:true,
      headers:{'Content-Type':'application/json','X-Reader-Token':noteToken},body:snapshot});
    if (!response.ok) throw new Error('Textbox could not be saved to PDF');
    try { if (localStorage.getItem(draftPrefix+note.id) === snapshot) localStorage.removeItem(draftPrefix+note.id); } catch {}
    $('notice').textContent = '';
  }).catch(error => { $('notice').textContent = error.message+' — your draft is kept locally.'; });
  return saveQueue;
}
notesReady.then(() => {
  for (const key of Object.keys(localStorage).filter(k => k.startsWith(draftPrefix))) {
    try {
      const pending = JSON.parse(localStorage.getItem(key));
      const existing = notes.find(n => n.id === pending.id);
      if (existing) {
        Object.assign(existing,pending);
        const old = document.querySelector(`[data-note="${pending.id}"]`);
        if (old?.nextElementSibling?.classList.contains('note-preview')) old.nextElementSibling.remove();
        old?.remove();
      }
      else notes.push(pending);
      if (pending.text.trim()) renderNote(pending);
      else notes = notes.filter(n => n.id !== pending.id);
      saveNote(pending);
    } catch {}
  }
});
document.addEventListener('keydown', event => {
  if (event.isComposing || event.repeat || event.ctrlKey || event.metaKey || event.altKey ||
      event.target.closest('input,textarea,[contenteditable]')) return;
  if (event.key.toLowerCase() === 't') { event.preventDefault(); dismiss(); setTextMode(!textMode); }
  if (event.key === 'Escape') setTextMode(false);
});
viewer.addEventListener('click', async event => {
  if (!textMode || event.target.closest('.note,.note-preview')) return;
  const sheet = event.target.closest('.sheet');
  if (!sheet) return;
  event.preventDefault(); event.stopImmediatePropagation();
  setTextMode(false);
  await notesReady;
  if (!noteToken) return;
  const index = Number(sheet.dataset.index), box = sheet.getBoundingClientRect();
  const x = Math.min(.96,Math.max(0,(event.clientX-box.left)/box.width));
  const y = Math.min(.96,Math.max(0,(event.clientY-box.top)/box.height));
  const note = {id:crypto.randomUUID(),page:book.pages[index].page,text:'',x,y,
    w:Math.min(.32,1-x),h:Math.min(.04,1-y),font_size:36};
  notes.push(note);
  const field = renderNote(note); field.focus({preventScroll:true});
}, {capture:true});
window.addEventListener('pagehide', () => {
  for (const note of notes) if (noteSaves.has(note.id)) saveNote(note);
});
