"""Generate a self-contained HTML form from a FormSchema.

The exported HTML file works offline in any browser. Customers fill it out and
click Submit to download a JSON file that can be imported back into the system.
"""

from __future__ import annotations

import html
import json

from .models import FieldType, FormSchema


def generate_html_form(schema: FormSchema) -> str:
    """Return a complete HTML document string for the given schema."""
    meta = json.dumps({
        "schema_id": schema.id,
        "schema_version": schema.version,
        "schema_name": schema.name,
    })

    sections_html = []
    for section in schema.sections:
        questions_html = []
        for q in section.questions:
            conditions_attr = ""
            if q.conditions:
                conditions_attr = html.escape(json.dumps(
                    [{"question_id": c.question_id, "operator": c.operator, "value": c.value}
                     for c in q.conditions]
                ))

            required_attr = "required" if q.required else ""
            required_label = ' <span class="required">*</span>' if q.required else ' <span class="optional">(optional)</span>'
            help_html = f'<div class="help-text">{html.escape(q.help_text)}</div>' if q.help_text else ""

            input_html = _render_input(q)

            cond_div = f' data-conditions="{conditions_attr}"' if conditions_attr else ""
            questions_html.append(
                f'<div class="question" data-qid="{html.escape(q.id)}"{cond_div}>\n'
                f'  <label>{html.escape(q.text)}{required_label}</label>\n'
                f'  {help_html}\n'
                f'  {input_html}\n'
                f'  <div class="error-msg" style="display:none;">This field is required.</div>\n'
                f'</div>'
            )

        sec_desc = f'<p class="section-desc">{html.escape(section.description)}</p>' if section.description else ""
        sections_html.append(
            f'<fieldset>\n'
            f'  <legend>{html.escape(section.title)}</legend>\n'
            f'  {sec_desc}\n'
            f'  {"".join(questions_html)}\n'
            f'</fieldset>'
        )

    form_desc = f'<p class="form-desc">{html.escape(schema.description)}</p>' if schema.description else ""

    return _HTML_TEMPLATE.format(
        title=html.escape(schema.name),
        description=form_desc,
        meta=html.escape(meta),
        sections="".join(sections_html),
    )


def _render_input(q) -> str:
    """Return the HTML input element(s) for a question."""
    name = html.escape(q.id)
    req = "required" if q.required else ""

    match q.field_type:
        case FieldType.DROPDOWN:
            opts = ''.join(
                f'<option value="{html.escape(o)}">{html.escape(o)}</option>'
                for o in q.options
            )
            return f'<select name="{name}" {req}><option value="">-- Select --</option>{opts}</select>'

        case FieldType.MULTI_SELECT:
            checks = ''.join(
                f'<label class="check-label"><input type="checkbox" name="{name}" value="{html.escape(o)}"> {html.escape(o)}</label>'
                for o in q.options
            )
            return f'<div class="multi-select" data-name="{name}" {"data-required" if q.required else ""}>{checks}</div>'

        case FieldType.YES_NO:
            return (
                f'<div class="radio-group">'
                f'<label class="radio-label"><input type="radio" name="{name}" value="Yes" {req}> Yes</label>'
                f'<label class="radio-label"><input type="radio" name="{name}" value="No"> No</label>'
                f'</div>'
            )

        case FieldType.TEXT:
            return f'<input type="text" name="{name}" {req}>'

        case FieldType.TEXTAREA:
            return f'<textarea name="{name}" rows="4" {req}></textarea>'

        case FieldType.DATE:
            return f'<input type="date" name="{name}" {req}>'

        case FieldType.NUMBER:
            return f'<input type="number" name="{name}" {req}>'

        case _:
            return f'<input type="text" name="{name}" {req}>'


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 24px; background: #f8f9fa; color: #1a1a2e; }}
  h1 {{ margin-bottom: 8px; color: #1a1a2e; }}
  .form-desc {{ margin-bottom: 24px; color: #555; }}
  fieldset {{ border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 20px; background: #fff; }}
  legend {{ font-size: 1.2em; font-weight: 600; padding: 0 8px; color: #1a1a2e; }}
  .section-desc {{ color: #666; margin-bottom: 12px; font-size: 0.9em; }}
  .question {{ margin-bottom: 16px; }}
  .question.hidden {{ display: none; }}
  .question label {{ display: block; font-weight: 500; margin-bottom: 4px; }}
  .required {{ color: #e74c3c; }}
  .optional {{ color: #999; font-weight: normal; font-size: 0.85em; }}
  .help-text {{ color: #888; font-size: 0.85em; margin-bottom: 4px; }}
  input[type="text"], input[type="number"], input[type="date"], select, textarea {{
    width: 100%; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 1em; font-family: inherit;
  }}
  input:focus, select:focus, textarea:focus {{ outline: none; border-color: #4a90d9; box-shadow: 0 0 0 2px rgba(74,144,217,0.2); }}
  .question.invalid input, .question.invalid select, .question.invalid textarea {{ border-color: #e74c3c; box-shadow: 0 0 0 2px rgba(231,76,60,0.2); }}
  .question.invalid .error-msg {{ display: block !important; color: #e74c3c; font-size: 0.85em; margin-top: 4px; }}
  .radio-group, .multi-select {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 4px 0; }}
  .radio-label, .check-label {{ font-weight: normal; display: flex; align-items: center; gap: 4px; cursor: pointer; }}
  .customer-info {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
  .customer-info h2 {{ font-size: 1.1em; margin-bottom: 12px; }}
  .confirmation {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
  .confirmation label {{ cursor: pointer; }}
  .btn-row {{ display: flex; gap: 12px; }}
  button {{ padding: 10px 24px; border: none; border-radius: 4px; font-size: 1em; cursor: pointer; font-weight: 500; }}
  .btn-submit {{ background: #4a90d9; color: #fff; }}
  .btn-submit:hover {{ background: #357abd; }}
  .btn-save {{ background: #f0f0f0; color: #333; border: 1px solid #ccc; }}
  .btn-save:hover {{ background: #e0e0e0; }}
  .error-summary {{ background: #fdf0f0; border: 1px solid #e74c3c; border-radius: 8px; padding: 16px; margin-top: 16px; display: none; }}
  .error-summary h3 {{ color: #e74c3c; margin-bottom: 8px; }}
  .error-summary ul {{ margin-left: 20px; color: #c0392b; }}
  .success {{ background: #f0fdf4; border: 1px solid #22c55e; border-radius: 8px; padding: 20px; margin-top: 16px; text-align: center; display: none; }}
  .success h3 {{ color: #16a34a; }}
</style>
</head>
<body>

<h1>{title}</h1>
{description}

<form id="intakeForm" novalidate>
<input type="hidden" id="schemaMeta" value="{meta}">

<div class="customer-info">
  <h2>Your Information</h2>
  <div class="question">
    <label>Your Name / Organization</label>
    <input type="text" name="_customer_name" id="customerName">
  </div>
</div>

{sections}

<div class="confirmation">
  <label><input type="checkbox" id="signOff"> I confirm that the information provided above is accurate and complete.</label>
</div>

<div class="btn-row">
  <button type="submit" class="btn-submit">Submit</button>
  <button type="button" class="btn-save" onclick="saveDraft()">Save Draft</button>
</div>

<div class="error-summary" id="errorSummary">
  <h3>Please complete the following required fields:</h3>
  <ul id="errorList"></ul>
</div>

<div class="success" id="successMsg">
  <h3>Response saved!</h3>
  <p>Your JSON file has been downloaded. Please send it to your account team.</p>
</div>

</form>

<script>
const META = JSON.parse(document.getElementById('schemaMeta').value);

// --- Progressive disclosure ---
function evaluateConditions() {{
  document.querySelectorAll('.question[data-conditions]').forEach(function(el) {{
    var conds = JSON.parse(el.dataset.conditions);
    var visible = conds.every(function(c) {{
      var val = getFieldValue(c.question_id);
      if (val === null || val === '') return false;
      switch (c.operator) {{
        case 'equals': return val === c.value;
        case 'not_equals': return val !== c.value;
        case 'contains': return Array.isArray(val) ? val.includes(c.value) : val === c.value;
        case 'in': return Array.isArray(c.value) ? c.value.includes(val) : val === c.value;
        default: return true;
      }}
    }});
    el.classList.toggle('hidden', !visible);
  }});
}}

function getFieldValue(qid) {{
  var radios = document.querySelectorAll('input[type="radio"][name="' + qid + '"]');
  if (radios.length) {{
    for (var r of radios) if (r.checked) return r.value;
    return null;
  }}
  var checks = document.querySelectorAll('input[type="checkbox"][name="' + qid + '"]');
  if (checks.length) {{
    var vals = [];
    checks.forEach(function(c) {{ if (c.checked) vals.push(c.value); }});
    return vals.length ? vals : null;
  }}
  var el = document.querySelector('[name="' + qid + '"]');
  return el ? (el.value || null) : null;
}}

document.getElementById('intakeForm').addEventListener('input', evaluateConditions);
document.getElementById('intakeForm').addEventListener('change', evaluateConditions);
evaluateConditions();

// --- Collect answers ---
function collectAnswers() {{
  var answers = {{}};
  document.querySelectorAll('.question[data-qid]').forEach(function(el) {{
    if (el.classList.contains('hidden')) return;
    var qid = el.dataset.qid;
    var val = getFieldValue(qid);
    if (val !== null && val !== '') answers[qid] = val;
  }});
  return answers;
}}

// --- Validation ---
function validate() {{
  var errors = [];
  document.querySelectorAll('.question.invalid').forEach(function(el) {{ el.classList.remove('invalid'); }});

  document.querySelectorAll('.question[data-qid]').forEach(function(el) {{
    if (el.classList.contains('hidden')) return;
    var qid = el.dataset.qid;
    var reqInput = el.querySelector('[required]');
    var reqMulti = el.querySelector('.multi-select[data-required]');
    if (!reqInput && !reqMulti) return;

    var val = getFieldValue(qid);
    if (val === null || val === '' || (Array.isArray(val) && val.length === 0)) {{
      el.classList.add('invalid');
      var label = el.querySelector('label').textContent.replace(' *', '').replace(' (optional)', '');
      errors.push(label);
    }}
  }});
  return errors;
}}

// --- Submit ---
document.getElementById('intakeForm').addEventListener('submit', function(e) {{
  e.preventDefault();
  var errors = validate();
  var summary = document.getElementById('errorSummary');
  var errorList = document.getElementById('errorList');

  if (errors.length) {{
    errorList.innerHTML = errors.map(function(e) {{ return '<li>' + e + '</li>'; }}).join('');
    summary.style.display = 'block';
    summary.scrollIntoView({{ behavior: 'smooth' }});
    return;
  }}
  summary.style.display = 'none';

  if (!document.getElementById('signOff').checked) {{
    alert('Please confirm the information is accurate before submitting.');
    return;
  }}

  downloadJSON('submitted');
}});

// --- Save draft ---
function saveDraft() {{
  downloadJSON('draft');
}}

function downloadJSON(status) {{
  var payload = {{
    schema_id: META.schema_id,
    schema_version: META.schema_version,
    schema_name: META.schema_name,
    status: status,
    customer_name: document.getElementById('customerName').value || null,
    answers: collectAnswers(),
    signed_off: status === 'submitted',
    exported_at: new Date().toISOString()
  }};

  var blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: 'application/json' }});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  var name = (payload.customer_name || 'response').replace(/[^a-zA-Z0-9]/g, '_');
  a.download = META.schema_name.replace(/[^a-zA-Z0-9]/g, '_') + '_' + name + '.json';
  a.click();
  URL.revokeObjectURL(url);

  if (status === 'submitted') {{
    document.getElementById('successMsg').style.display = 'block';
  }}
}}
</script>
</body>
</html>"""
