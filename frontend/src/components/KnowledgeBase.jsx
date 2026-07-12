import { useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { Icon } from './Icon';
import { EmptyState, Spinner, StatusBadge, formatBytes, formatDate, formatNumber } from './ui';

const acceptedExtensions = ['pdf', 'docx', 'txt', 'html', 'htm'];

function extensionOf(name = '') {
  return name.split('.').pop()?.toLowerCase() || 'file';
}

function collectDocumentIds(payload) {
  if (!payload || typeof payload !== 'object') return [];
  if (Array.isArray(payload.document_ids)) return payload.document_ids;
  const items = Array.isArray(payload.documents) ? payload.documents : Array.isArray(payload.files) ? payload.files : [];
  const ids = items.map((item) => item?.document_id || item?.id).filter(Boolean);
  const single = payload.document_id || payload.id;
  return single ? [...ids, single] : ids;
}

function UploadQueue({ files, removeFile, busy }) {
  if (!files.length) return null;
  return (
    <div className="upload-queue">
      {files.map((file) => (
        <div className="queued-file" key={`${file.name}-${file.size}-${file.lastModified}`}>
          <span className={`file-type file-${extensionOf(file.name)}`}>{extensionOf(file.name).slice(0, 4)}</span>
          <div><strong>{file.name}</strong><small>{formatBytes(file.size)}</small></div>
          {busy ? <Spinner size={17} /> : (
            <button onClick={() => removeFile(file)} aria-label={`Remove ${file.name}`} type="button"><Icon name="close" size={16} /></button>
          )}
        </div>
      ))}
    </div>
  );
}

export function KnowledgeBase({ documents, loading, onRefresh, notify }) {
  const [queuedFiles, setQueuedFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [autoIndex, setAutoIndex] = useState(true);
  const [selectedIds, setSelectedIds] = useState([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const inputRef = useRef(null);

  const counts = useMemo(() => ({
    total: documents.length,
    indexed: documents.filter((item) => ['indexed', 'ready', 'complete', 'completed'].includes(item.status)).length,
    processing: documents.filter((item) => ['processing', 'indexing', 'pending', 'uploaded'].includes(item.status)).length,
    chunks: documents.reduce((sum, item) => sum + (Number(item.chunks) || 0), 0),
  }), [documents]);

  const filteredDocuments = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return documents.filter((item) => {
      const matchesSearch = !needle || item.name.toLowerCase().includes(needle) || item.type.toLowerCase().includes(needle);
      const isIndexed = ['indexed', 'ready', 'complete', 'completed'].includes(item.status);
      const matchesStatus = statusFilter === 'all' || (statusFilter === 'indexed' ? isIndexed : !isIndexed);
      return matchesSearch && matchesStatus;
    });
  }, [documents, search, statusFilter]);

  const addFiles = (incoming) => {
    const existing = new Set(queuedFiles.map((file) => `${file.name}-${file.size}-${file.lastModified}`));
    const valid = [...incoming].filter((file) => acceptedExtensions.includes(extensionOf(file.name)));
    const rejected = [...incoming].length - valid.length;
    if (rejected) notify(`${rejected} unsupported file${rejected === 1 ? ' was' : 's were'} skipped.`, 'danger');
    setQueuedFiles((current) => [
      ...current,
      ...valid.filter((file) => !existing.has(`${file.name}-${file.size}-${file.lastModified}`)),
    ]);
  };

  const upload = async () => {
    if (!queuedFiles.length || uploading) return;
    setUploading(true);
    try {
      const payload = await api.uploadDocuments(queuedFiles);
      const duplicateCount = Number(payload?.duplicates?.length || payload?.duplicate_count || 0);
      const ids = collectDocumentIds(payload);
      const uploadErrors = Array.isArray(payload?.errors) ? payload.errors : [];
      if (!ids.length) {
        const detail = uploadErrors[0]?.error ? ` ${uploadErrors[0].error}` : '';
        notify(`No documents were accepted.${detail}`, 'danger');
        return;
      }
      let indexFailures = [];
      if (autoIndex) {
        const indexPayload = await api.indexDocuments(ids);
        indexFailures = (Array.isArray(indexPayload?.results) ? indexPayload.results : [])
          .filter((item) => item?.status === 'failed');
      }
      const problemCount = uploadErrors.length + indexFailures.length;
      notify(
        `${ids.length} document${ids.length === 1 ? '' : 's'} accepted${autoIndex ? ' and indexed' : ''}${duplicateCount ? `; ${duplicateCount} duplicate${duplicateCount === 1 ? '' : 's'} detected` : ''}${problemCount ? `; ${problemCount} item${problemCount === 1 ? '' : 's'} reported an error` : ''}.`,
        problemCount ? 'danger' : 'success',
      );
      setQueuedFiles([]);
      await onRefresh();
    } catch (error) {
      notify(error.message || 'Documents could not be uploaded.', 'danger');
    } finally {
      setUploading(false);
    }
  };

  const indexSelected = async () => {
    if (!selectedIds.length || indexing) return;
    setIndexing(true);
    try {
      await api.indexDocuments(selectedIds);
      notify(`${selectedIds.length} document${selectedIds.length === 1 ? '' : 's'} queued for indexing.`);
      setSelectedIds([]);
      await onRefresh();
    } catch (error) {
      notify(error.message || 'Indexing could not be started.', 'danger');
    } finally {
      setIndexing(false);
    }
  };

  const toggleSelection = (id) => {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  const allFilteredSelected = filteredDocuments.length > 0 && filteredDocuments.every((item) => selectedIds.includes(item.id));
  const toggleAll = () => {
    const visibleIds = filteredDocuments.map((item) => item.id);
    setSelectedIds((current) => allFilteredSelected
      ? current.filter((id) => !visibleIds.includes(id))
      : [...new Set([...current, ...visibleIds])]);
  };

  return (
    <div className="knowledge-page">
      <section className="knowledge-summary">
        <article><span className="summary-icon blue"><Icon name="library" size={19} /></span><div><strong>{formatNumber(counts.total)}</strong><small>Total documents</small></div></article>
        <article><span className="summary-icon green"><Icon name="check" size={19} /></span><div><strong>{formatNumber(counts.indexed)}</strong><small>Ready to search</small></div></article>
        <article><span className="summary-icon amber"><Icon name="refresh" size={19} /></span><div><strong>{formatNumber(counts.processing)}</strong><small>Pending / processing</small></div></article>
        <article><span className="summary-icon violet"><Icon name="layers" size={19} /></span><div><strong>{formatNumber(counts.chunks)}</strong><small>Indexed chunks</small></div></article>
      </section>

      <section className="upload-section panel-card">
        <div className="section-heading">
          <div><span className="eyebrow">Ingestion pipeline</span><h2>Add knowledge sources</h2><p>Upload enterprise documents. Metadata, page references, and content hashes are preserved during indexing.</p></div>
          <div className="pipeline-steps" aria-label="Ingestion pipeline">
            <span><Icon name="upload" size={14} /> Parse</span><Icon name="chevron" size={13} />
            <span><Icon name="layers" size={14} /> Chunk</span><Icon name="chevron" size={13} />
            <span><Icon name="database" size={14} /> Index</span>
          </div>
        </div>

        <div
          className={`drop-zone ${dragging ? 'dragging' : ''}`}
          onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => { event.preventDefault(); if (event.currentTarget === event.target) setDragging(false); }}
          onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}
        >
          <input
            accept=".pdf,.docx,.txt,.html,.htm"
            hidden
            multiple
            onChange={(event) => { addFiles(event.target.files); event.target.value = ''; }}
            ref={inputRef}
            type="file"
          />
          <span className="drop-icon"><Icon name="upload" size={25} /></span>
          <div><strong>Drop files here, or <button onClick={() => inputRef.current?.click()} type="button">browse</button></strong><span>PDF, DOCX, TXT, or HTML</span></div>
        </div>

        <UploadQueue
          files={queuedFiles}
          busy={uploading}
          removeFile={(file) => setQueuedFiles((current) => current.filter((item) => item !== file))}
        />

        {queuedFiles.length > 0 && (
          <div className="upload-actions">
            <label className="toggle-control">
              <input type="checkbox" checked={autoIndex} onChange={(event) => setAutoIndex(event.target.checked)} disabled={uploading} />
              <span className="toggle-track"><span /></span>
              Index automatically after upload
            </label>
            <div>
              <button className="secondary-button" onClick={() => setQueuedFiles([])} disabled={uploading} type="button">Clear</button>
              <button className="primary-button" onClick={upload} disabled={uploading} type="button">
                {uploading ? <><Spinner size={16} /> Uploading…</> : <><Icon name="upload" size={16} /> Upload {queuedFiles.length} file{queuedFiles.length === 1 ? '' : 's'}</>}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="documents-section panel-card">
        <div className="documents-header">
          <div><h2>Documents</h2><p>Sources available to the retrieval pipeline.</p></div>
          <div className="documents-actions">
            {selectedIds.length > 0 && (
              <button className="primary-button compact" onClick={indexSelected} disabled={indexing} type="button">
                {indexing ? <Spinner size={15} /> : <Icon name="bolt" size={15} />} Index selected ({selectedIds.length})
              </button>
            )}
            <button className="icon-button bordered" onClick={onRefresh} aria-label="Refresh documents" type="button"><Icon name="refresh" size={17} /></button>
          </div>
        </div>

        <div className="table-toolbar">
          <label className="search-field"><Icon name="search" size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents…" /></label>
          <div className="filter-tabs">
            {['all', 'indexed', 'pending'].map((filter) => (
              <button key={filter} className={statusFilter === filter ? 'active' : ''} onClick={() => setStatusFilter(filter)} type="button">
                {filter === 'all' ? 'All' : filter === 'indexed' ? 'Indexed' : 'Needs indexing'}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="table-loading"><Spinner /><span>Loading documents…</span></div>
        ) : filteredDocuments.length === 0 ? (
          <EmptyState
            icon={documents.length ? 'search' : 'library'}
            title={documents.length ? 'No documents match' : 'Your knowledge base is empty'}
            description={documents.length ? 'Try changing the search term or status filter.' : 'Upload a PDF, DOCX, TXT, or HTML file to create your first searchable source.'}
            action={!documents.length ? <button className="primary-button" onClick={() => inputRef.current?.click()} type="button"><Icon name="upload" size={16} /> Choose files</button> : null}
          />
        ) : (
          <div className="documents-table-wrap">
            <table className="documents-table">
              <thead><tr>
                <th className="checkbox-cell"><input type="checkbox" checked={allFilteredSelected} onChange={toggleAll} aria-label="Select all visible documents" /></th>
                <th>Document</th><th>Status</th><th>Pages</th><th>Chunks</th><th>Uploaded</th>
              </tr></thead>
              <tbody>
                {filteredDocuments.map((document) => (
                  <tr key={document.id}>
                    <td className="checkbox-cell"><input type="checkbox" checked={selectedIds.includes(document.id)} onChange={() => toggleSelection(document.id)} aria-label={`Select ${document.name}`} /></td>
                    <td><div className="document-name"><span className={`file-type file-${extensionOf(document.name)}`}>{extensionOf(document.name).slice(0, 4)}</span><div><strong title={document.name}>{document.name}</strong><small>{document.size !== null ? formatBytes(document.size) : document.type}</small></div></div></td>
                    <td><StatusBadge status={document.status} /></td>
                    <td>{formatNumber(document.pages)}</td>
                    <td>{formatNumber(document.chunks)}</td>
                    <td>{formatDate(document.uploadedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
