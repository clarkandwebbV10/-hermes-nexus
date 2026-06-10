import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FolderTree,
  Activity,
  Settings,
  Search,
  Zap,
  Terminal as TerminalIcon,
} from 'lucide-react';

const Themes = {
  default: { name: 'Linear Dark' },
  hogwarts: { name: 'Hogwarts Magic' },
  marvel: { name: 'Avengers Initiative' },
  batman: { name: 'Gotham Night' },
};

export default function NexusOS() {
  const [theme, setTheme] = useState('default');
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <div data-theme={theme} className="min-h-screen p-6 font-sans text-nexus-text transition-colors duration-500">
      {/* TOP BAR */}
      <header className="flex items-center justify-between mb-8 bg-nexus-card p-4 rounded-2xl border border-white/10 shadow-2xl backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="bg-nexus-accent p-2 rounded-lg text-black">
            <Zap size={24} fill="currentColor" />
          </div>
          <h1 className="text-2xl font-bold tracking-tighter">HERMES <span className="text-nexus-accent">NEXUS</span></h1>
        </div>

        <div className="flex items-center gap-4">
          <div className="relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-nexus-muted" size={18} />
            <input 
              type="text" 
              placeholder="Command Nexus..." 
              className="bg-nexus-bg border border-white/10 rounded-full py-2 pl-10 pr-4 w-64 focus:outline-none focus:border-nexus-accent transition-all"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          
          <select 
            className="bg-nexus-bg border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none text-nexus-text"
            value={theme} 
            onChange={(e) => setTheme(e.target.value)}
          >
            {Object.entries(Themes).map(([id, { name }]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
        </div>
      </header>

      {/* MAIN GRID */}
      <main className="grid grid-cols-12 gap-6 h-[calc(100vh-150px)]">
        
        {/* SIDEBAR: Files & Folders */}
        <motion.section 
          initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
          className="col-span-3 bg-nexus-card rounded-3xl border border-white/10 p-6 flex flex-col gap-6 overflow-hidden"
        >
          <div className="flex items-center gap-2 text-nexus-muted font-semibold uppercase text-xs tracking-wider">
            <FolderTree size={16} /> System Explorer
          </div>
          <div className="flex-1 overflow-y-auto space-y-2 pr-2">
            {['Documents', 'Projects', 'Archives', 'Config', 'Secrets'].map((folder) => (
              <div 
                key={folder}
                className="group flex items-center justify-between p-3 rounded-xl hover:bg-white/5 cursor-pointer transition-colors border border-transparent hover:border-white/10"
              >
                <div className="flex items-center gap-3">
                  <FolderTree size={18} className="text-nexus-accent" />
                  <span className="text-sm">{folder}</span>
                </div>
                <Settings size={14} className="opacity-0 group-hover:opacity-100 text-nexus-muted" />
              </div>
            ))}
          </div>
          <div className="p-4 bg-nexus-bg rounded-2xl border border-white/10">
            <div className="text-xs text-nexus-muted mb-2">Quick Action</div>
            <button className="w-full py-2 bg-nexus-accent text-black rounded-lg font-bold text-sm hover:brightness-110 transition-all flex items-center justify-center gap-2">
              <TerminalIcon size={16} /> Run Analysis
            </button>
          </div>
        </motion.section>

        {/* CENTER: Jobs & Activity */}
        <motion.section 
          initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
          className="col-span-6 flex flex-col gap-6"
        >
          <div className="bg-nexus-card rounded-3xl border border-white/10 p-6 flex-1 overflow-hidden flex flex-col">
             <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2 text-nexus-muted font-semibold uppercase text-xs tracking-wider">
                  <Activity size={16} /> Active Operations
                </div>
                <span className="text-[10px] bg-nexus-accent/20 text-nexus-accent px-2 py-1 rounded-full border border-nexus-accent/30">
                  LIVE
                </span>
             </div>
             <div className="flex-1 overflow-y-auto space-y-4 pr-2">
                {[
                  { name: 'Cron: Web Scraper', status: 'Running', progress: 65, color: 'bg-blue-500' },
                  { name: 'Agent: Researcher', status: 'Idle', progress: 100, color: 'bg-green-500' },
                  { name: 'Cron: System Backup', status: 'Pending', progress: 10, color: 'bg-yellow-500' },
                  { name: 'Agent: Code Review', status: 'Running', progress: 32, color: 'bg-blue-500' },
                ].map((job, i) => (
                  <div key={i} className="bg-nexus-bg p-4 rounded-2xl border border-white/5 flex flex-col gap-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">{job.name}</span>
                      <span className="text-xs text-nexus-muted">{job.status}</span>
                    </div>
                    <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }} animate={{ width: `${job.progress}%` }}
                        className={`h-full ${job.color}`}
                      />
                    </div>
                  </div>
                ))}
             </div>
          </div>
        </motion.section>

        {/* RIGHT: System Health & Tools */}
        <motion.section 
          initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
          className="col-span-3 flex flex-col gap-6"
        >
          <div className="bg-nexus-card rounded-3xl border border-white/10 p-6">
            <div className="text-nexus-muted font-semibold uppercase text-xs tracking-wider mb-4">System Pulse</div>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm">CPU</span>
                <span className="text-sm font-mono text-nexus-accent">24%</span>
              </div>
              <div className="h-1 w-full bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-nexus-accent w-1/4" />
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Memory</span>
                <span className="text-sm font-mono text-nexus-accent">4.2GB / 16GB</span>
              </div>
              <div className="h-1 w-full bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-nexus-accent w-1/4" />
              </div>
            </div>
          </div>

          <div className="bg-nexus-card rounded-3xl border border-white/10 p-6 flex-1">
            <div className="text-nexus-muted font-semibold uppercase text-xs tracking-wider mb-4">Nexus Tools</div>
            <div className="grid grid-cols-2 gap-3">
              {['Web Search', 'Vision', 'Image Gen', 'Memory', 'Terminal', 'Code Exec'].map((tool) => (
                <button 
                  key={tool}
                  className="p-3 bg-nexus-bg border border-white/10 rounded-xl text-xs hover:border-nexus-accent transition-all text-left"
                >
                  {tool}
                </button>
              ))}
            </div>
          </div>
        </motion.section>

      </main>
    </div>
  );
}
