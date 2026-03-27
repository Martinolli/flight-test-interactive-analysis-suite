import { useState, useEffect, useRef } from 'react';
import Sidebar from '../components/Sidebar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { ApiService, Document } from '../services/api';
import { useToast } from '../components/ui/toast';
import { ConfirmDialog } from '../components/ui/confirm-dialog';
import {
  BookOpen,
  Upload,
  Trash2,
  FileText,
  CheckCircle,
  AlertCircle,
  Loader2,
  Plus,
  X,
  Info,
} from 'lucide-react';

const DOC_TYPES = [
  { value: 'standard', label: 'Standard (MIL-STD, DO-xxx, FAR/CS)' },
  { value: 'handbook', label: 'Handbook / Manual' },
  { value: 'report', label: 'Test Report' },
  { value: 'procedure', label: 'Test Procedure' },
  { value: 'other', label: 'Other' },
];

function formatBytes(bytes: number | null): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: Document['status'] }) {
  if (status === 'ready')
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
        <CheckCircle className="w-3 h-3" /> Ready
      </span>
    );
  if (status === 'processing')
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
        <Loader2 className="w-3 h-3 animate-spin" /> Processing
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
      <AlertCircle className="w-3 h-3" /> Error
    </span>
  );
}

export default function DocumentLibrary() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUploadPanel, setShowUploadPanel] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDocType, setUploadDocType] = useState('standard');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast, ToastContainer } = useToast();

  useEffect(() => {
    loadDocuments();
  }, []);

  async function loadDocuments() {
    setLoading(true);
    try {
      const docs = await ApiService.getDocuments();
      setDocuments(docs);
    } catch (err) {
      showToast((err as Error).message || 'Failed to load documents', 'error');
    } finally {
      setLoading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      setUploadFile(file);
      if (!uploadTitle) setUploadTitle(file.name.replace(/\.pdf$/i, ''));
      setShowUploadPanel(true);
    } else {
      showToast('Only PDF files are supported for the document library.', 'error');
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      if (!uploadTitle) setUploadTitle(file.name.replace(/\.pdf$/i, ''));
      setShowUploadPanel(true);
    }
  }

  async function handleUpload() {
    if (!uploadFile) return;
    setUploading(true);
    setUploadProgress(0);
    try {
      const doc = await ApiService.uploadDocument(
        uploadFile,
        { title: uploadTitle || undefined, doc_type: uploadDocType, description: uploadDescription || undefined },
        setUploadProgress
      );
      showToast(
        `"${doc.title || doc.filename}" uploaded. Processing ${doc.total_pages ?? '?'} pages…`,
        'success'
      );
      setDocuments((prev) => [doc, ...prev]);
      resetUploadForm();
    } catch (err) {
      showToast((err as Error).message || 'Upload failed', 'error');
    } finally {
      setUploading(false);
    }
  }

  function resetUploadForm() {
    setUploadFile(null);
    setUploadTitle('');
    setUploadDocType('standard');
    setUploadDescription('');
    setUploadProgress(0);
    setShowUploadPanel(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await ApiService.deleteDocument(deleteTarget.id);
      setDocuments((prev) => prev.filter((d) => d.id !== deleteTarget.id));
      showToast(`"${deleteTarget.title || deleteTarget.filename}" removed from library.`, 'success');
    } catch (err) {
      showToast((err as Error).message || 'Delete failed', 'error');
    } finally {
      setDeleteTarget(null);
    }
  }

  const readyCount = documents.filter((d) => d.status === 'ready').length;
  const processingCount = documents.filter((d) => d.status === 'processing').length;

  return (
    <Sidebar>
      <ToastContainer />
      <ConfirmDialog
        open={!!deleteTarget}
        title="Remove Document"
        description={`Remove "${deleteTarget?.title || deleteTarget?.filename}" from the library? All associated chunks and embeddings will be deleted permanently.`}
        confirmLabel="Remove"
        variant="destructive"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      <div className="p-8 max-w-6xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Document Library</h1>
            <p className="text-gray-600 mt-1">
              Upload flight test standards, handbooks, and procedures for AI-powered analysis
            </p>
          </div>
          <Button onClick={() => setShowUploadPanel(true)} className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Add Document
          </Button>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <Card className="p-4">
            <p className="text-sm text-gray-500">Total Documents</p>
            <p className="text-2xl font-bold text-gray-900">{documents.length}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-gray-500">Ready for Queries</p>
            <p className="text-2xl font-bold text-green-600">{readyCount}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-gray-500">Processing</p>
            <p className="text-2xl font-bold text-blue-600">{processingCount}</p>
          </Card>
        </div>

        {/* Upload panel */}
        {showUploadPanel && (
          <Card className="mb-6 border-blue-200 bg-blue-50">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Upload New Document</CardTitle>
                <button onClick={resetUploadForm} className="text-gray-400 hover:text-gray-600">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Drop zone */}
              <div
                className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                  dragging ? 'border-blue-500 bg-blue-100' : 'border-gray-300 hover:border-blue-400'
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={handleFileSelect}
                />
                {uploadFile ? (
                  <div className="flex items-center justify-center gap-2 text-blue-700">
                    <FileText className="w-5 h-5" />
                    <span className="font-medium">{uploadFile.name}</span>
                    <span className="text-gray-500">({formatBytes(uploadFile.size)})</span>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-gray-600 text-sm">Drop a PDF here or click to browse</p>
                  </>
                )}
              </div>

              {/* Metadata fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                  <input
                    type="text"
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    placeholder="e.g. MIL-STD-1797A Flying Qualities"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
                  <select
                    value={uploadDocType}
                    onChange={(e) => setUploadDocType(e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {DOC_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                <textarea
                  value={uploadDescription}
                  onChange={(e) => setUploadDescription(e.target.value)}
                  rows={2}
                  placeholder="Brief description of the document content…"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>

              {/* Progress bar */}
              {uploading && (
                <div>
                  <div className="flex justify-between text-xs text-gray-600 mb-1">
                    <span>Uploading & processing…</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={resetUploadForm} disabled={uploading}>
                  Cancel
                </Button>
                <Button onClick={handleUpload} disabled={!uploadFile || uploading}>
                  {uploading ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processing…</>
                  ) : (
                    <><Upload className="w-4 h-4 mr-2" /> Upload & Index</>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Info banner */}
        <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg mb-6 text-sm text-amber-800">
          <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <p>
            Documents are parsed with <strong>Docling</strong> (IBM), which preserves tables,
            section numbering, and cross-references. Large documents (200+ pages) may take 1–3 minutes
            to process. Once status shows <strong>Ready</strong>, they are available for AI queries
            and flight test analysis.
          </p>
        </div>

        {/* Document table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="w-5 h-5" />
              Indexed Documents
            </CardTitle>
            <CardDescription>
              Standards, handbooks, and procedures available for AI-powered analysis
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600 mr-2" />
                <span className="text-gray-500">Loading library…</span>
              </div>
            ) : documents.length === 0 ? (
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center cursor-pointer hover:border-blue-400 transition-colors"
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => { setShowUploadPanel(true); fileInputRef.current?.click(); }}
              >
                <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 font-medium">No documents in the library yet</p>
                <p className="text-gray-400 text-sm mt-1">
                  Drop a PDF here or click <strong>Add Document</strong> to get started
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-2 font-medium text-gray-600">Document</th>
                      <th className="text-left py-3 px-2 font-medium text-gray-600">Type</th>
                      <th className="text-right py-3 px-2 font-medium text-gray-600">Pages</th>
                      <th className="text-right py-3 px-2 font-medium text-gray-600">Chunks</th>
                      <th className="text-right py-3 px-2 font-medium text-gray-600">Size</th>
                      <th className="text-center py-3 px-2 font-medium text-gray-600">Status</th>
                      <th className="text-left py-3 px-2 font-medium text-gray-600">Added</th>
                      <th className="py-3 px-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc) => (
                      <tr key={doc.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-2">
                          <div className="flex items-start gap-2">
                            <FileText className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                            <div>
                              <p className="font-medium text-gray-900">{doc.title || doc.filename}</p>
                              {doc.title && (
                                <p className="text-xs text-gray-400">{doc.filename}</p>
                              )}
                              {doc.description && (
                                <p className="text-xs text-gray-500 mt-0.5">{doc.description}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-gray-600 capitalize">{doc.doc_type || '—'}</td>
                        <td className="py-3 px-2 text-right text-gray-600">{doc.total_pages ?? '—'}</td>
                        <td className="py-3 px-2 text-right text-gray-600">{doc.total_chunks ?? '—'}</td>
                        <td className="py-3 px-2 text-right text-gray-600">{formatBytes(doc.file_size_bytes)}</td>
                        <td className="py-3 px-2 text-center">
                          <StatusBadge status={doc.status} />
                          {doc.error_message && (
                            <p className="text-xs text-red-500 mt-1">{doc.error_message}</p>
                          )}
                        </td>
                        <td className="py-3 px-2 text-gray-500 text-xs">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3 px-2">
                          <button
                            onClick={() => setDeleteTarget(doc)}
                            className="text-gray-400 hover:text-red-500 transition-colors"
                            title="Remove document"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
}
