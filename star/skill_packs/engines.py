"""Other-engine skill packs: Bevy, GameMaker, Defold, Phaser, Three.js, UEFN/Verse, Minecraft and more.

Each pack is an ordinary skill pack folder (`engine-<slug>/SKILL.md` + `references/sources.md`), distilled from
the engine's official documentation (long-form research with sources: docs/research/engines/).

Routing is stricter than for the Roblox packs: a pack is considered only when the prompt NAMES its engine
(ENGINE_CONTEXTS), so Roblox prompts and unrelated prompts are unchanged. All of them are off by default
(not in DEFAULT_ENABLED) until the evaluation gate has measured them; switch them on with
STAR_SKILL_PACKS=engines (every engine pack plus the default packs) or a comma list of names.
"""
from __future__ import annotations

import re

_I = re.IGNORECASE

# Pack name -> regex that identifies the engine itself. Must never match an ordinary Roblox or English prompt.
# Pack name -> regex that identifies the engine itself. Must never match an ordinary Roblox or English prompt.
ENGINE_CONTEXTS: dict[str, re.Pattern] = {
    "engine-alternatives-2026": re.compile(
        '\\b(?:fyrox|ebiten(?:gine)?|macroquad|gdevelop|kaplay(?:\\.?js)?|kaboom\\.?js|excalibur(?:\\.?js|\\s+(?:engine|0\\.\\d+))|wicked\\s*engine|redot(?:\\s+engine)?|armory3d|upbge|unity\\s+alternatives?)\\b', _I),
    "engine-babylonjs": re.compile(
        '\\bbabylon\\.?js\\b|\\bbabylonjs\\b|@babylonjs/|\\bBABYLON\\.[A-Z]\\w+', _I),
    "engine-bevy": re.compile(
        '\\b(?:bevy|bevy_ecs|bevy_ui|bevy_app)\\b', _I),
    "engine-cocos-creator": re.compile(
        '\\bcocos(?:\\s*creator|2d(?:-x)?|\\s*4|\\s*engine)?\\b|\\bccclass\\b|from\\s+[\'\\"]cc[\'\\"]', _I),
    "engine-construct3": re.compile(
        '\\b(?:construct\\s?3|construct\\s?2|scirra|c3p|capx)\\b|\\bconstruct\\s+(?:engine|editor|game\\s+engine|event\\s+sheets?)\\b', _I),
    "engine-defold": re.compile(
        '\\bdefold\\b', _I),
    "engine-flax": re.compile(
        '\\b(?:flax\\s*engine|flaxengine|flax\\s*editor|flax\\s*1\\.\\d+|FlaxEngine)\\b', _I),
    "engine-gamemaker": re.compile(
        '\\b(?:gamemaker|game\\s+maker\\s+(?:studio|lts|20\\d\\d)|gms\\s?2|gml|yoyo\\s?games)\\b', _I),
    "engine-heaps": re.compile(
        '\\b(?:heaps\\.io|heapsio|heaps\\s+(?:engine|framework|game\\s+framework|[12]\\.\\d+)|haxe\\s+heaps|heaps\\s+(?:with|and|in)\\s+haxe|hxd\\.(?:app|res|key|save)|hashlink|h2d\\.(?:bitmap|object|scene|text|tile|anim|interactive|flow)|h3d\\.(?:scene|prim|vector4?|mat))\\b', _I),
    "engine-love2d": re.compile(
        '(?:\\blove2d\\b|\\bl[öo]ve\\s*2d\\b|\\blöve\\b|\\blove\\.(?:graphics|update|draw|load|physics|filesystem|keyboard|conf)\\b)', _I),
    "engine-minecraft": re.compile(
        '\\b(?:minecraft|neoforge|fabric\\s+(?:mod|api|loader|loom)|fabricmc|mcfunction|bedrock\\s+(?:add-?ons?|edition|script(?:ing)?\\s+api|behaviou?r\\s+packs?)|@minecraft/server)\\b', _I),
    "engine-monogame": re.compile(
        '\\b(?:monogame|FNA|FNA3D|KNI|XNA|Microsoft\\.Xna\\.Framework)\\b', _I),
    "engine-o3de": re.compile(
        '\\b(?:o3de|open\\s*3d\\s*engine|lumberyard)\\b', _I),
    "engine-phaser": re.compile(
        '\\bphaser(?:js|\\.io)?\\s*(?:[234](?:\\.\\d+)*|ce|editor)\\b|\\bphaser\\.(?:game|scene|physics|math|types|gameobjects)\\b|\\b(?:in|with|using|for)\\s+phaser\\b|@phaserjs/', _I),
    "engine-pico8": re.compile(
        '(?:\\b(?:pico-?8|picotron|tic-?80|fantasy\\s+console|p8\\s*lua|lexaloffle)\\b|\\.p8(?:\\.png)?\\b)', _I),
    "engine-pixijs": re.compile(
        '\\bpixi(?:\\.?js)?\\b|@pixi/|\\bpixi-react\\b', _I),
    "engine-playcanvas": re.compile(
        '\\bplay\\s?canvas\\b|@playcanvas/|\\bpc\\.(?:createScript|Application|Entity|Vec3|AppBase)\\b|\\bfrom\\s+[\'\\"]playcanvas[\'\\"]', _I),
    "engine-raylib": re.compile(
        '\\b(?:raylib|raygui|raymath|rlgl|raylib-cs|pyray|raylib-rs)\\b', _I),
    "engine-renpy": re.compile(
        "\\bren'?py\\b|\\.rpyc?\\b", _I),
    "engine-rpgmaker-mz": re.compile(
        '\\b(?:rpg\\s?maker(?:\\s?(?:mz|mv|unite|vx\\s?ace|vx|xp))?|rmmz|rmmv|rpgmz)\\b', _I),
    "engine-sbox": re.compile(
        '(?:\\bs&box\\b|\\bs\\s*&\\s*box\\b|\\bsbox\\b|\\bsbox\\.game\\b|\\bsandbox\\s+(?:engine|game)\\s+facepunch\\b|\\bfacepunch\\s+s&?box\\b)', _I),
    "engine-sdl3": re.compile(
        '\\b(?:SDL3|SDL\\s?3(?:\\.\\d+)?|SDL3_(?:image|ttf|mixer|net)|libsdl)\\b', _I),
    "engine-solar2d": re.compile(
        '\\b(?:solar2d|corona\\s+sdk|coronasdk|corona\\s+labs)\\b', _I),
    "engine-stride": re.compile(
        '\\b(?:stride3d|stride\\s*(?:engine|game\\s*engine|4\\.\\d)|xenko|stride\\s*game\\s*studio|Stride\\.(?:Engine|BepuPhysics|Physics|Core|Input|UI))\\b', _I),
    "engine-threejs": re.compile(
        '\\bthree\\.?js\\b|\\bthreejs\\b|\\breact-three-fiber\\b|@react-three/|\\bfrom\\s+[\'\\"]three(?:/webgpu|/tsl|/addons)?[\'\\"]|\\bTHREE\\.(?:Scene|Mesh|WebGLRenderer|WebGPURenderer|Object3D|Vector3)\\b', _I),
    "engine-uefn-verse": re.compile(
        '\\b(?:uefn|fortnite|verse\\s+(?:lang(?:uage)?|code|device|script(?:s|ing)?)|creative_device|unreal\\s+editor\\s+for\\s+fortnite)\\b', _I),
    "engine-ugc-platforms": re.compile(
        '\\b(?:horizon\\s+worlds?|meta\\s+horizon|hytopia|rec\\s?room|zepeto|manticore|core\\s+games|the\\s+sandbox\\s+(?:game\\s*maker|platform|metaverse)|dreams\\s+(?:ps4|media\\s+molecule))\\b', _I),
}

# Pack name -> regex of the engine's distinctive API names (used to rank packs when several engines are named).
ENGINE_TOPICS: dict[str, re.Pattern] = {
    "engine-alternatives-2026": re.compile(
        '(?:\\b(?:ebiten\\.RunGame|vector\\.FillRect|inpututil|ScriptTrait|GameResult|is_key_down|get_frame_time|onKeyDown|ex\\.(?:Actor|Engine|Keys|Scene)|onPreUpdate|startServer|PlayerEvent|DefaultPlayerEntity|runtimeScene|gdjs)\\b|next_frame\\(\\)\\.await|\\bkaplay\\(|\\bwi::\\w+)', _I),
    "engine-babylonjs": re.compile(
        '\\b(?:MeshBuilder|ArcRotateCamera|HemisphericLight|HavokPlugin|HavokPhysics|PhysicsAggregate|PhysicsShapeType|PhysicsImpostor|onBeforeRenderObservable|runRenderLoop|AdvancedDynamicTexture|WebGPUEngine|ImportMeshAsync|SceneLoader|NodeMaterial|ShadowGenerator|debugLayer|AnimationGroup|Playground)\\b', _I),
    "engine-bevy": re.compile(
        '\\b(?:Commands|Query|ResMut|add_systems|App::new|MessageWriter|MessageReader|ButtonInput|DefaultPlugins|Single|EntityEvent|despawn|delta_secs|add_observer|add_message|Camera2d|Sprite)\\b', _I),
    "engine-cocos-creator": re.compile(
        '@ccclass\\b|@property\\b|\\b_decorator\\b|\\bUITransform\\b|\\bRigidBody2D\\b|\\bContact2DType\\b|\\bresources\\.load\\b|\\bassetManager\\b|\\binstantiate\\(|\\bdirector\\.loadScene\\b|\\bInput\\.EventType\\b|\\bscheduleOnce\\b|\\bwechatgame\\b', _I),
    "engine-construct3": re.compile(
        '\\b(?:runOnStartup|beforeprojectstart|afteranylayoutstart|IRuntime|IWorldInstance|IObjectClass|InstanceType\\.\\w+|instVars|getFirstInstance|getAllInstances|createInstance|globalVars|callFunction|event\\s+sheets?|behaviors\\.\\w+|runtime\\.dt)\\b', _I),
    "engine-defold": re.compile(
        '\\b(?:msg\\.post|go\\.property|go\\.(?:get|set)_position|go\\.animate|go\\.delete|factory\\.create|collectionproxy|collection\\s+proxy|acquire_input_focus|on_message|on_input|gui\\.get_node|sys\\.save|sys\\.get_save_file|game\\.project)\\b', _I),
    "engine-flax": re.compile(
        '\\b(?:FlaxEngine|KeyboardKeys|OnLateFixedUpdate|PhysicsColliderActor|TriggerEnter|CharacterController|UIControl|UICanvas|NetworkReplicator|NetworkReplicated|NetworkRpc|PrefabManager|Game\\s*Cooker|Flax\\.Build|ProductLocalFolder|Visject)\\b', _I),
    "engine-gamemaker": re.compile(
        '\\b(?:instance_create_(?:layer|depth)|instance_destroy|draw_self|draw\\s+gui|keyboard_check(?:_pressed)?|place_meeting|instance_place|move_and_collide|room_goto|vk_(?:left|right|up|down|space)|array_length|json_stringify|json_parse|ds_(?:list|map)_\\w+)\\b', _I),
    "engine-heaps": re.compile(
        '\\b(?:hxd\\.App|hxd\\.Res\\.init(?:Embed|Local|Pak)|hxd\\.Key\\.is(?:Down|Pressed|Released)|h2d\\.(?:Bitmap|Tile|Text|Anim|Interactive|Flow|Graphics|Scene)|h3d\\.(?:scene\\.Mesh|prim\\.Cube|Vector4)|s2d|s3d|scaleMode|LetterBox|hlsdl|hldx|HxSL|hxbit|DefaultFont)\\b', _I),
    "engine-love2d": re.compile(
        '\\blove\\.(?:load|update|draw|graphics|physics|filesystem|keyboard|mouse|keypressed|conf|window|audio|math)\\b|\\bconf\\.lua\\b', _I),
    "engine-minecraft": re.compile(
        '(?:ModInitializer|DeferredRegister|BuiltInRegistries|ResourceKey|Identifier\\.fromNamespaceAndPath|Item\\.Properties|@Mixin|@Inject|CreativeModeTab|NeoForge\\.EVENT_BUS|fabric\\.mod\\.json|neoforge\\.mods\\.toml|pack\\.mcmeta|world\\.afterEvents|system\\.beforeEvents|system\\.runInterval|manifest\\.json|setDynamicProperty)', _I),
    "engine-monogame": re.compile(
        '\\b(?:SpriteBatch|GraphicsDeviceManager|LoadContent|Content\\.Load|Texture2D|Keyboard\\.GetState|GameTime|ElapsedGameTime|SpriteFont|ContentBuilder|GetContentCollection|WildcardRule|MGCB|mgcb|mgdesktopgl|xnb)\\b', _I),
    "engine-o3de": re.compile(
        '\\b(?:AZ::Component|AZ_COMPONENT|AZ::TickBus|TickBus|EBus|BusConnect|BusDisconnect|TransformBus|BehaviorContext|SerializeContext|Script\\s*Canvas|LyShine|PhysX5|AutoComponent|InputEventNotificationBus|EntityBus|OnEntityActivated|SaveDataRequestBus|prefab|Gem)\\b', _I),
    "engine-phaser": re.compile(
        '\\bthis\\.physics\\.add\\.|\\bthis\\.(?:tweens|cameras|anims|load|input\\.keyboard)\\b|\\bcreateCursorKeys\\b|\\bsetTint(?:Fill|Mode)?\\b|\\bArcade\\b|\\bstaticGroup\\b|\\bpreload\\(\\)|\\bsetVelocity[XY]?\\b|\\brefreshBody\\b|\\bfilters\\.(?:internal|external)\\b', _I),
    "engine-pico8": re.compile(
        '(?:\\b(?:_update60|_init|_draw|cartdata|dget|dset|pmem|tline|palt|fillp|BOOT)\\b|\\b(?:btnp?|spr|sspr|mget|mset|fget)\\(|\\bTIC\\(\\))', _I),
    "engine-pixijs": re.compile(
        '\\bapp\\.init\\(|\\bapp\\.(?:canvas|stage|ticker)\\b|\\bAssets\\.(?:load|add|loadBundle)\\b|\\bGraphics(?:Context)?\\b|\\beventMode\\b|\\bParticleContainer\\b|\\bcacheAsTexture\\b|\\bTextureSource\\b|\\bbeginFill\\b|\\bdeltaTime\\b', _I),
    "engine-playcanvas": re.compile(
        '\\b(?:createScript|scriptName|extends\\s+Script|ScriptType|addComponent|rigidbody|collisionstart|triggerenter|WasmModule|app\\.root|findByTag|isPressed|KEY_[A-Z]|gsplat|AppBase|createGraphicsDevice|postInitialize|postUpdate|@attribute|\\.mjs)\\b', _I),
    "engine-raylib": re.compile(
        '\\b(?:InitWindow|WindowShouldClose|BeginDrawing|EndDrawing|BeginMode2D|BeginMode3D|GetFrameTime|DrawText|DrawRectangle\\w*|LoadTexture|LoadModelAnimations|UpdateModelAnimation|GuiButton|CheckCollision\\w+|IsKeyDown|Camera2D)\\b', _I),
    "engine-renpy": re.compile(
        '\\b(?:label\\s+\\w+|jump\\s+\\w+|call\\s+screen|show\\s+screen|init\\s+python|persistent\\.\\w+|renpy\\.\\w+|textbutton|imagebutton|transform\\s+\\w+|Character\\(|rollback|_return)', _I),
    "engine-rpgmaker-mz": re.compile(
        '\\b(?:PluginManager|registerCommand|Scene_(?:Map|Battle|Menu|Title|Base|Boot)|Window_(?:Base|Selectable|Command|Message)|Game_(?:Interpreter|Party|Actor|Player|Map|System|Variables|Switches)|DataManager|ImageManager|plugins\\.js)\\b|\\$(?:game|data)\\w+|@target\\s+MZ\\b|@command\\b|@arg\\b', _I),
    "engine-sbox": re.compile(
        '(?:\\bPanelComponent\\b|\\bBuildHash\\b|\\[Sync\\b|\\[Rpc\\.(?:Broadcast|Host|Owner)\\]|\\bIsProxy\\b|\\bNetworkSpawn\\b|\\bGameObjectSystem\\b|\\bITriggerListener\\b|\\bScene\\.Trace\\b|\\bInput\\.AnalogMove\\b|\\bWorldPosition\\b|\\bOnFixedUpdate\\b|\\bNetworkMode\\b|\\bSyncFlags\\b|\\bsbproj\\b)', _I),
    "engine-sdl3": re.compile(
        '\\b(?:SDL_AppInit|SDL_AppIterate|SDL_AppEvent|SDL_AppQuit|SDL_MAIN_USE_CALLBACKS|SDL_EVENT_\\w+|SDL_RenderTexture|SDL_RenderFillRect|SDL_CreateWindowAndRenderer|SDL_GetKeyboardState|SDL_CreateGPUDevice|SDL_IOStream|SDL_Gamepad|TTF_RenderText_\\w+|MIX_\\w+|IMG_LoadTexture)\\b', _I),
    "engine-solar2d": re.compile(
        '\\b(?:display\\.new\\w+|composer\\.\\w+|physics\\.addBody|transition\\.to|timer\\.performWithDelay|Runtime:addEventListener|system\\.DocumentsDirectory|setFillColor|build\\.settings)\\b', _I),
    "engine-stride": re.compile(
        '\\b(?:SyncScript|AsyncScript|StartupScript|Script\\.NextFrame|Game\\.UpdateTime|WarpElapsed|Stride\\.BepuPhysics|BodyComponent|StaticComponent|CharacterComponent|IContactHandler|NoContactResponse|ISimulationUpdate|UIComponent|FindVisualChildOfType|Game\\s*Studio|sdsl|sdfx)\\b', _I),
    "engine-threejs": re.compile(
        '\\b(?:WebGLRenderer|WebGPURenderer|BufferGeometry|BoxGeometry|MeshStandardMaterial|MeshPhysicalMaterial|PerspectiveCamera|OrbitControls|GLTFLoader|setAnimationLoop|outputColorSpace|SRGBColorSpace|InstancedMesh|BatchedMesh|AnimationMixer|Raycaster|TSL|NodeMaterial|three/addons|useFrame)\\b', _I),
    "engine-uefn-verse": re.compile(
        '(?:creative_device|<suspends>|<decides>|<transacts>|<persistable>|weak_map\\(|@editable|OnBegin<override>|GetPlayspace\\(|GetFortCharacter\\[|trigger_device|button_device|score_manager_device|\\.Subscribe\\(|\\brace:|\\bsync:|\\bspawn\\{|Sleep\\(|scene\\s+graph|class<final_super>\\(component\\))', _I),
    "engine-ugc-platforms": re.compile(
        '(?:horizon/core|propsDefinition|connectCodeBlockEvent|CodeBlockEvents|Component\\.register|PropTypes\\.|NetworkEvent|LocalEvent|startServer\\(|PlayerEvent\\.JOINED_WORLD|DefaultPlayerEntity|world\\.loadMap|player\\.ui\\.|circuits\\s*v2|ZepetoScriptBehaviour)', _I),
}
