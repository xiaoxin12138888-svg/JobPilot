import { useState } from 'react';

import { REJECTION_REASON_LABELS } from '@jobpilot/api-client';
import type { Application, RejectionReason, UpdateApplicationInput } from '@jobpilot/api-client';

export function ApplicationOutcomeForm({
  application,
  onSave,
}: {
  application: Application;
  onSave(input: UpdateApplicationInput): Promise<void>;
}) {
  const [outcomeNote, setOutcomeNote] = useState(application.outcomeNote ?? '');
  const [rejectionReason, setRejectionReason] = useState<RejectionReason | ''>(
    application.rejectionReason ?? '',
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save() {
    setSaving(true);
    setSaved(false);
    const input: UpdateApplicationInput = { outcomeNote: outcomeNote.trim() || null };
    if (application.status === 'rejected') {
      input.rejectionReason = rejectionReason || null;
    }
    try {
      await onSave(input);
      setSaved(true);
    } catch {
      // The parent displays the stable local error and keeps this form retryable.
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="application-outcome">
      <h3>结果记录</h3>
      <label className="field">
        <span>{application.status === 'offer' ? 'Offer 说明' : '结果说明'}</span>
        <textarea
          value={outcomeNote}
          onChange={(event) => setOutcomeNote(event.target.value)}
          placeholder={application.status === 'offer' ? '薪资、入职时间、是否接受等' : undefined}
        />
      </label>
      {application.status === 'rejected' && (
        <>
          <label className="field">
            <span>原因记录（由用户填写）</span>
            <select
              value={rejectionReason}
              onChange={(event) => setRejectionReason(event.target.value as RejectionReason | '')}
            >
              <option value="">未记录</option>
              {Object.entries(REJECTION_REASON_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <p className="outcome-guidance">这是你记录的已知情况或自我判断，不是系统判定。</p>
        </>
      )}
      <button
        type="button"
        className="button secondary full-width"
        disabled={saving}
        onClick={() => void save()}
      >
        {saving ? '正在保存…' : '保存结果记录'}
      </button>
      {saved && (
        <p className="success-note" role="status">
          结果记录已保存。
        </p>
      )}
    </div>
  );
}
