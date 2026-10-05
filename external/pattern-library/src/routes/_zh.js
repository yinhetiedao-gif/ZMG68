import original from "./_lang.js";
// Keep the upstream string keys; localize controls without changing pattern data.
const strings = {
  ...original.strings,
  title: "小芒图案库",
  heading: "选择图案，调整参数，<span>导出你的设计</span>",
  description: "现成的 330 款可平铺 SVG 图案，点击即可编辑。",
  description2: "调整颜色、比例、间距和角度，预览实时更新。",
  description3: "支持下载 SVG / PNG；制造和 STL 继续使用原图案实验室。",
  keywords: "小芒图案库, SVG, 图案, 参数, PNG",
  searchPattern: "搜索图案（可使用英文名称）", pressFocus: "按 / 开始搜索",
  patterns: "款图案", license: "MIT 开源许可", free: "免费使用",
  filter: "筛选", sort: "排序", filterMode: "图案模式", filterColors: "颜色数量",
  allModes: "全部模式", allColors: "全部颜色", stroke: "线宽", fill: "填充",
  colors: "颜色", latest: "最新", oldest: "最早", updateDate: "更新时间",
  zoom: "比例", hSpacing: "横向间距", vSpacing: "纵向间距",
  hPosition: "横向位置", vPosition: "纵向位置", angle: "角度",
  inspire: "随机灵感", random: "随机参数", reset: "恢复默认",
  copy: "复制", copyCSS: "复制 CSS", copySVG: "复制 SVG",
  download: "下载", downloadSVG: "下载当前图案 SVG", downloadPNG: "下载当前图案 PNG",
  dimensions: "导出尺寸", width: "宽度", height: "高度", hide: "隐藏面板",
  lock: "锁定颜色", unlock: "解锁颜色", square: "方角", rounded: "圆角", join: "连接方式",
};
export default { strings };
