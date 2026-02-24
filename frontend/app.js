const API_BASE = localStorage.getItem('API_BASE') || 'http://localhost:8000';
const outEl = document.querySelector('#output pre');

const renderCollegeTabs = (data) => {
  const sections = ['fees', 'placement', 'cutoff', 'infrastructure', 'reviews'];
  let html = `Institute: ${data.institute.slug}\nCourse: ${data.course.course_name} (${data.course.course_id})\n\n`;
  sections.forEach((s) => {
    html += `=== ${s.toUpperCase()} (parsed) ===\n${JSON.stringify(data.parsed[s], null, 2)}\n\n`;
  });
  html += `=== RAW HTML FILES ===\n${JSON.stringify(data.pages, null, 2)}`;
  outEl.textContent = html;
};

document.getElementById('runBtn').onclick = async () => {
  const college_name = document.getElementById('college').value;
  const course_name = document.getElementById('course').value;
  outEl.textContent = 'Running scrape...';
  const res = await fetch(`${API_BASE}/api/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ college_name, course_name })
  });
  const data = await res.json();
  renderCollegeTabs(data);
};

document.getElementById('compareBtn').onclick = async () => {
  outEl.textContent = 'Generating AI comparison...';
  const colleges = JSON.parse(document.getElementById('compareInput').value || '[]');
  const res = await fetch(`${API_BASE}/api/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ colleges })
  });
  const data = await res.json();
  outEl.textContent = data.report;
};
