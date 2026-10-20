# 2026-10-21 软件目录扩充验收

本轮新增 206 个软件身份，均已纳入覆盖门禁。配置总数从 494 增至 700；最终上线数量与有效入口以发布快照为准。

候选来自人工整理的重要软件缺口，对照 Homebrew Cask、Scoop 和 WinGet 当前元数据。按稳定 ID、名称和官方主页去重；拒绝已停用目录、错误架构、过期或无效地址。没有将同一软件的 Windows/macOS 版本重复计数，也没有把 .NET SDK 附带的运行库重复计为新软件。

新条目采用 package_manifest 持续刷新版本、资产和上游 SHA256；明确官方 CDN 域名后仍复验响应。直链不可用时，仅在官方入口页独立通过身份与下载入口验证后降级，页面入口与安装包直链分别标注。Mendeley 的下载页降级使用 Elsevier 官方安装说明（旧 service.elsevier.com 已迁往 elsevier.support），仍由相同身份与下载入口规则复验。完整安装包未下载验签，不把上游 SHA256 当作已完成本地校验。

待进一步处理且未纳入本批新增计数：GitKraken、SourceTree、XYplorer、GPU-Z、Qt Creator、Resilio Sync、SketchUp 等，其下载入口、平台或来源仍需复核。CPU-Z、SSMS、System Informer 的 WinGet 清单路径未能唯一定位，也没有伪造成功。后续继续补齐，不能把本轮清单当作所有重要软件已经穷尽。

## 已上线验收

- GitHub 仓库 About 的 Website 已设置为 [FastAPI Cloud 国际站](https://latest-softwares-064facea.fastapicloud.dev)。
- 国际版从 **393 增至 599 项**，实际新增 **206 项**；仓库目录共 700 项。新增项中 87 项采用 Windows 来源，119 项采用 macOS 来源；没有声称每项都覆盖所有操作系统。
- 所有 206 个新增软件在发布快照中至少有一个仍有效的已验证入口。必收录门禁实际通过 300/301；唯一人工批准的发布例外为 Photoshop，其下载入口保持禁用。例外只适用于此次手动发布，不继承到后续定时运行。
- 国际版目前 580 项有至少一个可用入口，19 项旧条目待核验；936/972 个平台入口可用。不能把收录数量等同于有效下载数量。
- [同步、门禁及构建运行](https://github.com/funny-dog/latest-softwares/actions/runs/39485100737)与[FastAPI Cloud 部署运行](https://github.com/funny-dog/latest-softwares/actions/runs/39485504602)均成功，快照 ID 为 `bd70139a36828fe4e478`。
- HTTP 验收通过：首页字节与同一运行的 dist-intl artifact 完全一致，health/packages 返回同一快照；Photoshop API 返回 503，.NET SDK 下载跳转与快照 URL 一致；Turso 访问与下载计数未下降。
- 未打开实际网页进行人工交互验收，未完整下载安装包、验签或测试安装器。仍待补齐的候选保留在下文，不计入本轮新增成果。

| 软件 | ID | 本轮平台 | 持续更新来源 |
|---|---|---|---|
| Arc | `arc` | mac | brew: `arc` |
| Min | `min` | win-x64 | scoop: `extras/min` |
| Orion Browser | `orion` | mac | brew: `orion` |
| Pale Moon | `palemoon` | win-x64 | scoop: `extras/palemoon` |
| SeaMonkey | `seamonkey` | win-x64 | scoop: `extras/seamonkey` |
| Waterfox | `waterfox` | win-x64 | scoop: `extras/waterfox` |
| Wavebox | `wavebox` | mac-arm64 | brew: `wavebox` |
| Android Studio | `android-studio` | win-x64 | scoop: `extras/android-studio` |
| AWS CLI | `aws` | win-x64 | scoop: `main/aws` |
| Azure CLI | `azure-cli` | win-x64 | scoop: `main/azure-cli` |
| Microsoft Azure Storage Explorer | `azure-storage-explorer` | win-x64 | winget: `Microsoft.Azure.StorageExplorer` |
| BBEdit | `bbedit` | mac | brew: `bbedit` |
| Beyond Compare | `beyond-compare` | mac | brew: `beyond-compare` |
| Charles | `charles` | mac | brew: `charles` |
| CLion | `clion` | win-x64 | scoop: `extras/clion` |
| CMake | `cmake` | win-x64 | scoop: `main/cmake` |
| Composer | `composer` | win | scoop: `main/composer` |
| Amazon Corretto JDK 25 | `corretto-jdk` | win-x64 | winget: `Amazon.Corretto.25.JDK` |
| CotEditor | `coteditor` | mac | brew: `coteditor` |
| DataGrip | `datagrip` | mac-arm64 | brew: `datagrip` |
| DB Browser for SQLite | `db-browser-for-sqlite` | mac | brew: `db-browser-for-sqlite` |
| DbGate | `dbgate` | mac-universal | brew: `dbgate` |
| Deno | `deno` | win-x64 | scoop: `main/deno` |
| .NET SDK 10 | `dotnet-sdk` | win-x64 | winget: `Microsoft.DotNet.SDK.10` |
| Eclipse IDE for Java Developers | `eclipse-java` | win-x64 | scoop: `extras/eclipse-java` |
| Fork | `fork` | win | scoop: `extras/fork` |
| Geany | `geany` | mac-arm64 | brew: `geany` |
| GitButler | `gitbutler` | win-x64 | scoop: `extras/gitbutler` |
| Git Extensions | `gitextensions` | win-x64 | scoop: `extras/gitextensions` |
| GitHub Desktop | `github-desktop` | win-x64 | scoop: `extras/github` |
| Goland | `goland` | mac-arm64 | brew: `goland` |
| Gradle | `gradle` | win | scoop: `main/gradle` |
| HTTP Toolkit | `http-toolkit` | mac-arm64 | brew: `http-toolkit` |
| IntelliJ IDEA Ultimate | `intellij-idea` | win-x64 | scoop: `extras/idea` |
| Julia | `julia` | win-x64 | scoop: `main/julia` |
| Kate | `kate` | mac-arm64 | brew: `kate` |
| KDiff3 | `kdiff3` | win-x64 | scoop: `extras/kdiff3` |
| kubectl | `kubectl` | win-x64 | scoop: `main/kubectl` |
| Lens | `lens` | mac-arm64 | brew: `lens` |
| LLVM | `llvm` | win-x64 | scoop: `main/llvm` |
| MacTeX | `mactex-no-gui` | mac | brew: `mactex-no-gui` |
| Maven | `maven` | win | scoop: `main/maven` |
| Meld | `meld` | win-x64 | scoop: `extras/meld` |
| MongoDB Compass | `mongodb-compass` | win-x64 | scoop: `extras/mongodb-compass` |
| MySQL Workbench | `mysqlworkbench` | mac-arm64 | brew: `mysqlworkbench` |
| NetBeans IDE | `netbeans` | mac-arm64 | brew: `netbeans` |
| Ninja | `ninja` | win-x64 | scoop: `main/ninja` |
| Packer | `packer` | win-x64 | scoop: `main/packer` |
| pgAdmin4 | `pgadmin4` | mac-arm64 | brew: `pgadmin4` |
| PHP | `php` | win-x64 | scoop: `main/php` |
| JetBrains PhpStorm | `phpstorm` | mac-arm64 | brew: `phpstorm` |
| Podman Desktop | `podman-desktop` | mac-arm64 | brew: `podman-desktop` |
| Positron | `positron` | mac-arm64 | brew: `positron` |
| Postico | `postico` | mac | brew: `postico` |
| Proxyman | `proxyman` | mac | brew: `proxyman` |
| PyCharm | `pycharm` | win-x64 | scoop: `extras/pycharm` |
| Querious 4 | `querious` | mac | brew: `querious` |
| R | `r` | win-x64 | scoop: `main/r` |
| Rancher Desktop | `rancher` | mac-arm64 | brew: `rancher` |
| RapidAPI | `rapidapi` | mac | brew: `rapidapi` |
| Redis Insight | `redis-insight` | mac-arm64 | brew: `redis-insight` |
| JetBrains Rider | `rider` | win-x64 | scoop: `extras/rider` |
| RStudio | `rstudio` | win-x64 | scoop: `extras/rstudio` |
| RubyMine | `rubymine` | mac-arm64 | brew: `rubymine` |
| RustRover | `rustrover` | win-x64 | scoop: `extras/rustrover` |
| Rustup | `rustup` | win-x64 | scoop: `main/rustup` |
| Sequel Ace | `sequel-ace` | mac | brew: `sequel-ace` |
| SmartGit | `smartgit` | win-x64 | scoop: `extras/smartgit` |
| SQLiteStudio | `sqlitestudio` | win-x64 | scoop: `extras/sqlitestudio` |
| Studio 3T | `studio-3t` | mac-arm64 | brew: `studio-3t` |
| Sublime Merge | `sublime-merge` | win-x64 | scoop: `extras/sublime-merge` |
| Sublime Text | `sublime-text` | win-x64 | scoop: `extras/sublime-text` |
| Eclipse Temurin JDK 25 | `temurin-jdk` | win-x64 | winget: `EclipseAdoptium.Temurin.25.JDK` |
| TextMate | `textmate` | mac | brew: `textmate` |
| Vagrant | `vagrant` | win-x64 | scoop: `main/vagrant` |
| Microsoft Visual C++ Redistributable x64 | `vcredist-x64` | win-x64 | winget: `Microsoft.VCRedist.2015+.x64` |
| Visual Studio Community | `visual-studio-community` | win-x64 | winget: `Microsoft.VisualStudio.2022.Community` |
| WebStorm | `webstorm` | mac-arm64 | brew: `webstorm` |
| WinMerge | `winmerge` | win-x64 | scoop: `extras/winmerge` |
| Ableton Live Suite | `ableton-live-suite` | mac-universal | brew: `ableton-live-suite` |
| Acorn | `acorn` | mac | brew: `acorn` |
| AIMP | `aimp` | win-x64 | scoop: `extras/aimp` |
| Autodesk Fusion 360 | `autodesk-fusion` | mac | brew: `autodesk-fusion` |
| Bambu Studio | `bambu-studio` | win-x64 | scoop: `extras/bambu-studio` |
| Bitwig Studio | `bitwig-studio` | mac | brew: `bitwig-studio` |
| Canva | `canva` | mac-universal | brew: `canva` |
| Cap | `cap` | mac | brew: `cap` |
| Dopamine | `dopamine` | win | scoop: `extras/dopamine` |
| Elmedia Player | `elmedia-player` | mac | brew: `elmedia-player` |
| FL Studio | `fl-studio` | mac | brew: `fl-studio` |
| Kap | `kap` | mac-arm64 | brew: `kap` |
| Libresprite | `libresprite` | win-x64 | scoop: `extras/libresprite` |
| MeshLab | `meshlab` | win-x64 | scoop: `extras/meshlab` |
| Mixxx | `mixxx` | mac | brew: `mixxx` |
| MPC-BE | `mpc-be` | win-x64 | scoop: `extras/mpc-be` |
| MPC-HC | `mpc-hc` | win-x64 | scoop: `extras/mpc-hc-fork` |
| ocenaudio | `ocenaudio` | win-x64 | scoop: `extras/ocenaudio` |
| OpenToonz | `opentoonz` | win-x64 | scoop: `extras/opentoonz` |
| Orca Slicer | `orcaslicer` | win-x64 | scoop: `extras/orcaslicer` |
| Paintbrush | `paintbrush` | mac | brew: `paintbrush` |
| Pinta | `pinta` | win-x64 | scoop: `extras/pinta` |
| PrusaSlicer | `prusaslicer` | win-x64 | scoop: `extras/prusaslicer` |
| REAPER | `reaper` | win-x64 | scoop: `extras/reaper` |
| rekordbox | `rekordbox` | mac | brew: `rekordbox` |
| Screen Studio | `screen-studio` | mac-arm64 | brew: `screen-studio` |
| Sketch | `sketch` | mac | brew: `sketch` |
| UltiMaker Cura | `ultimaker-cura` | mac-arm64 | brew: `ultimaker-cura` |
| VirtualDJ | `virtualdj` | mac | brew: `virtualdj` |
| Cyberduck | `cyberduck` | mac | brew: `cyberduck` |
| Little Snitch | `little-snitch` | mac | brew: `little-snitch` |
| LuLu | `lulu` | mac | brew: `lulu` |
| Mountain Duck | `mountain-duck` | mac | brew: `mountain-duck` |
| Transmit | `transmit` | mac | brew: `transmit` |
| Asana | `asana` | mac-arm64 | brew: `asana` |
| Basecamp | `basecamp` | mac | brew: `basecamp` |
| Box Drive | `box-drive` | mac | brew: `box-drive` |
| BusyCal | `busycal` | mac | brew: `busycal` |
| Capacities | `capacities` | mac-arm64 | brew: `capacities` |
| Celestia | `celestia` | mac | brew: `celestia` |
| ClickUp | `clickup` | mac-arm64 | brew: `clickup` |
| EndNote | `endnote` | mac | brew: `endnote` |
| Evernote | `evernote` | mac | brew: `evernote` |
| Fantastical | `fantastical` | mac | brew: `fantastical` |
| Ferdium | `ferdium` | win-x64 | scoop: `extras/ferdium` |
| Franz | `franz` | mac-arm64 | brew: `franz` |
| GeoGebra | `geogebra` | win | scoop: `extras/geogebra` |
| Google Earth Pro | `google-earth-pro` | mac-x64 | brew: `google-earth-pro` |
| Hepta | `heptabase` | mac-arm64 | brew: `heptabase` |
| Internxt Drive | `internxt-drive` | mac | brew: `internxt-drive` |
| Itsycal | `itsycal` | mac | brew: `itsycal` |
| JabRef | `jabref` | win-x64 | scoop: `extras/jabref` |
| jamovi | `jamovi` | win-x64 | scoop: `extras/jamovi` |
| JASP | `jasp` | mac-arm64 | brew: `jasp` |
| MeetingBar | `meetingbar` | mac | brew: `meetingbar` |
| MEGAsync | `megasync` | win-x64 | scoop: `extras/megasync` |
| Mendeley | `mendeley` | win-x64 | scoop: `extras/mendeley` |
| Nextcloud | `nextcloud` | win-x64 | scoop: `extras/nextcloud` |
| Notesnook | `notesnook` | win-x64 | scoop: `extras/notesnook` |
| OmniFocus | `omnifocus` | mac | brew: `omnifocus` |
| OmniGraffle | `omnigraffle` | mac | brew: `omnigraffle` |
| OmniPlan | `omniplan` | mac | brew: `omniplan` |
| ONLYOFFICE | `onlyoffice` | win-x64 | scoop: `extras/onlyoffice-desktopeditors` |
| ownCloud | `owncloud` | win-x64 | scoop: `extras/owncloud` |
| ReadCube Papers | `papers` | mac-arm64 | brew: `papers` |
| PDF Expert | `pdf-expert` | mac | brew: `pdf-expert` |
| PDFgear | `pdfgear` | win-x64 | scoop: `extras/pdfgear` |
| PDFsam Basic | `pdfsam-basic` | win-x64 | scoop: `extras/pdfsam` |
| Microsoft Power BI Desktop | `power-bi-desktop` | win-x64 | winget: `Microsoft.PowerBI` |
| QGIS | `qgis` | mac | brew: `qgis` |
| Rambox | `rambox` | win-x64 | scoop: `extras/rambox` |
| Sage | `sage` | mac-arm64 | brew: `sage` |
| Scrivener | `scrivener` | mac | brew: `scrivener` |
| Seadrive | `seadrive` | mac | brew: `seadrive` |
| Skim | `skim` | mac | brew: `skim` |
| SoftMaker FreeOffice | `softmaker-freeoffice` | mac | brew: `softmaker-freeoffice` |
| Standard Notes | `standard-notes` | win-x64 | scoop: `extras/standardnotes` |
| Stellarium | `stellarium` | win-x64 | scoop: `extras/stellarium` |
| Synology Drive | `synology-drive` | mac | brew: `synology-drive` |
| Taskade | `taskade` | mac-universal | brew: `taskade` |
| Texmaker | `texmaker` | win-x64 | scoop: `extras/texmaker` |
| TeXstudio | `texstudio` | win-x64 | scoop: `extras/texstudio` |
| Advanced Renamer | `advancedrenamer` | win-x64 | scoop: `extras/advancedrenamer` |
| AIDA64 Extreme | `aida64extreme` | win | scoop: `extras/aida64extreme` |
| Alfred | `alfred` | mac | brew: `alfred` |
| AltTab | `alt-tab` | mac | brew: `alt-tab` |
| Apparency | `apparency` | mac | brew: `apparency` |
| FreeMacSoft AppCleaner | `appcleaner` | mac | brew: `appcleaner` |
| Arq | `arq` | mac | brew: `arq` |
| Backblaze | `backblaze` | mac | brew: `backblaze` |
| Bartender | `bartender` | mac | brew: `bartender` |
| BetterTouchTool | `bettertouchtool` | mac | brew: `bettertouchtool` |
| BlockBlock | `blockblock` | mac | brew: `blockblock` |
| Carbon Copy Cloner | `carbon-copy-cloner` | mac | brew: `carbon-copy-cloner` |
| ChronoSync | `chronosync` | mac | brew: `chronosync` |
| CleanShot | `cleanshot` | mac | brew: `cleanshot` |
| Clipy | `clipy` | mac | brew: `clipy` |
| Commander One | `commander-one` | mac | brew: `commander-one` |
| Espanso | `espanso` | mac-universal | brew: `espanso` |
| ForkLift | `forklift` | mac | brew: `forklift` |
| FreeFileSync | `freefilesync` | mac | brew: `freefilesync` |
| Hammerspoon | `hammerspoon` | mac | brew: `hammerspoon` |
| Hidden Bar | `hiddenbar` | mac | brew: `hiddenbar` |
| HWiNFO | `hwinfo` | win-x64 | winget: `REALiX.HWiNFO` |
| HWMonitor | `hwmonitor` | win-x64 | scoop: `extras/hwmonitor` |
| Karabiner Elements | `karabiner-elements` | mac | brew: `karabiner-elements` |
| Keyboard Maestro | `keyboard-maestro` | mac | brew: `keyboard-maestro` |
| KnockKnock | `knockknock` | mac | brew: `knockknock` |
| LinearMouse | `linearmouse` | mac | brew: `linearmouse` |
| Mos | `mos` | mac | brew: `mos` |
| Multi Commander | `multicommander` | win-x64 | scoop: `extras/multicommander` |
| Multipass | `multipass` | mac | brew: `multipass` |
| OneCommander | `onecommander` | win | scoop: `extras/onecommander` |
| OverSight | `oversight` | mac | brew: `oversight` |
| Parallels Desktop | `parallels` | mac | brew: `parallels` |
| Paste | `paste` | mac | brew: `paste` |
| PopClip | `popclip` | mac | brew: `popclip` |
| Q-Dir | `q-dir` | win-x64 | scoop: `extras/q-dir` |
| Scroll Reverser | `scroll-reverser` | mac | brew: `scroll-reverser` |
| Shottr | `shottr` | mac | brew: `shottr` |
| SuperDuper! | `superduper` | mac | brew: `superduper` |
| Suspicious Package | `suspicious-package` | mac | brew: `suspicious-package` |
| Syncovery | `syncovery` | mac | brew: `syncovery` |
| TestDisk | `testdisk` | win | scoop: `extras/testdisk` |
| Total Commander | `totalcommander` | win-x64 | scoop: `extras/totalcommander` |
| Yoink | `yoink` | mac | brew: `yoink` |
| Free Download Manager | `freedownloadmanager` | win-x64 | scoop: `extras/freedownloadmanager` |
