/**
 * FileTypeIcon — icon đại diện cho loại file theo phần mở rộng tên file.
 * Vẽ lại phong cách logo Microsoft Office (Word/Excel/PowerPoint) và PDF
 * bằng SVG inline, không phụ thuộc asset ngoài.
 */

type Props = {
  /** Tên file đầy đủ, dùng để lấy phần mở rộng. */
  fileName: string;
  /** Kích thước icon (px). Mặc định 32. */
  size?: number;
  className?: string;
};

interface Palette {
  light: string;
  mid: string;
  dark: string;
  badge: string;
  label: string;
  labelSize: number;
}

const PALETTES: Record<'word' | 'excel' | 'ppt' | 'pdf', Palette> = {
  word: { light: '#41A5EE', mid: '#2B7CD3', dark: '#185ABD', badge: '#185ABD', label: 'W', labelSize: 11 },
  excel: { light: '#33C481', mid: '#21A366', dark: '#107C41', badge: '#107C41', label: 'X', labelSize: 11 },
  ppt: { light: '#ED6C47', mid: '#D35230', dark: '#C43E1C', badge: '#C43E1C', label: 'P', labelSize: 11 },
  pdf: { light: '#FF7A6E', mid: '#E5252A', dark: '#C8102E', badge: '#C8102E', label: 'PDF', labelSize: 6.5 },
};

const extOf = (name: string) => {
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i + 1).toLowerCase() : '';
};

/** Icon kiểu Office: trang tài liệu nhiều dải màu + ô badge chữ cái bên trái. */
const OfficeGlyph = ({ p, size, className }: { p: Palette; size: number; className?: string }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    className={className}
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    {/* Trang tài liệu — 3 dải màu, ló ra bên phải badge */}
    <path d="M13 4h15a2 2 0 0 1 2 2v6H11V6a2 2 0 0 1 2-2Z" fill={p.light} />
    <rect x="11" y="12" width="19" height="8" fill={p.mid} />
    <path d="M11 20h19v6a2 2 0 0 1-2 2H13a2 2 0 0 1-2-2Z" fill={p.dark} />
    {/* Badge chữ cái */}
    <rect x="1.5" y="7" width="17" height="18" rx="2.5" fill={p.badge} />
    <text
      x="10"
      y="16.4"
      textAnchor="middle"
      dominantBaseline="central"
      fontFamily="'Segoe UI', Arial, sans-serif"
      fontWeight="700"
      fontSize={p.labelSize}
      fill="#fff"
    >
      {p.label}
    </text>
  </svg>
);

/** Icon mặc định: tài liệu xám có góc gấp. */
const GenericGlyph = ({ size, className }: { size: number; className?: string }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    className={className}
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path d="M8 4a2 2 0 0 1 2-2h9l9 9v17a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2Z" fill="#94A3B8" />
    <path d="M19 2l9 9h-7a2 2 0 0 1-2-2Z" fill="#CBD5E1" />
  </svg>
);

const FileTypeIcon = ({ fileName, size = 32, className }: Props) => {
  const ext = extOf(fileName);
  if (ext === 'doc' || ext === 'docx')
    return <OfficeGlyph p={PALETTES.word} size={size} className={className} />;
  if (ext === 'xls' || ext === 'xlsx' || ext === 'xlsm' || ext === 'csv')
    return <OfficeGlyph p={PALETTES.excel} size={size} className={className} />;
  if (ext === 'ppt' || ext === 'pptx')
    return <OfficeGlyph p={PALETTES.ppt} size={size} className={className} />;
  if (ext === 'pdf') return <OfficeGlyph p={PALETTES.pdf} size={size} className={className} />;
  return <GenericGlyph size={size} className={className} />;
};

export default FileTypeIcon;
