# App branding (source files)

| File | Use |
|------|-----|
| `icon_1024.png` | Master icon — regenerate Tauri sizes from this |
| `AppIcon.ico` | Windows ICO used for `icon.ico`, browser favicon, and embedded in the built `.exe` after rebuild |

Regenerate Tauri `frontend/src-tauri/icons/` after updating the master PNG:

```powershell
cd frontend
npm run tauri icon ..\assets\branding\icon_1024.png
```

Then copy `AppIcon.ico` over the generated ICO (optional, if you maintain a hand-tuned multi-size ICO):

```powershell
Copy-Item ..\assets\branding\AppIcon.ico src-tauri\icons\icon.ico -Force
```

Browser favicons in `frontend/public/` are copied from the icon set after regeneration.
