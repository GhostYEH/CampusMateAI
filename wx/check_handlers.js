const fs = require('fs');
const path = require('path');

function checkDir(dir) {
    if (!fs.existsSync(dir)) return;
    const files = fs.readdirSync(dir);
    for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory()) {
            checkDir(fullPath);
        } else if (file.endsWith('.wxml')) {
            const wxmlContent = fs.readFileSync(fullPath, 'utf8');
            const binds = [...wxmlContent.matchAll(/bind:?([a-zA-Z0-9]+)=['"]([^'"]+)['"]/g)];
            const jsPath = fullPath.replace('.wxml', '.ts');
            if (fs.existsSync(jsPath)) {
                const jsContent = fs.readFileSync(jsPath, 'utf8');
                for (const match of binds) {
                    const eventName = match[1];
                    const handlerName = match[2];
                    if (handlerName.includes('{{') || handlerName === '') continue; // skip dynamic binds
                    // simple check if handler exists in js
                    if (!jsContent.includes(handlerName)) {
                        console.log('Missing handler ' + handlerName + ' for event ' + eventName + ' in ' + jsPath);
                    }
                }
            }
        }
    }
}
const miniprogramDir = path.join(__dirname, 'miniprogram');
checkDir(path.join(miniprogramDir, 'pages'));
checkDir(path.join(miniprogramDir, 'components'));
checkDir(path.join(miniprogramDir, 'custom-tab-bar'));
console.log('Check finished.');
