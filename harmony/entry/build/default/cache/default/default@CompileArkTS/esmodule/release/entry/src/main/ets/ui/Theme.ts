export interface CampusPalette {
    background: string;
    surface: string;
    text: string;
    muted: string;
    primary: string;
    primaryHover: string;
    soft: string;
    line: string;
    accent: string;
    danger: string;
    success: string;
}
export const lightPalette: CampusPalette = {
    background: '#F6F8FA',
    surface: '#FFFFFFFF',
    text: '#1B2730',
    muted: '#667784',
    primary: '#5B68F2',
    primaryHover: '#4E5EDB',
    soft: '#EFF0FF',
    line: '#E2E7EC',
    accent: '#E08A4E',
    danger: '#C25450',
    success: '#4E8C6A'
};
export const darkPalette: CampusPalette = {
    background: '#09161C',
    surface: '#14272E',
    text: '#E8F0F4',
    muted: '#A6B5BE',
    primary: '#9CC7D0',
    primaryHover: '#B8DEE3',
    soft: '#1C3C45',
    line: '#2B424A',
    accent: '#F3B078',
    danger: '#E68780',
    success: '#79B492'
};
