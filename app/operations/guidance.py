from ..settings import TEXT

def briefing(site):
    if site['family']=='flood':
        d=site['depth']
        situation=f"If still rising: {site['depth_arrival_m']:.2f} m at nominal arrival; now {d['lo']:.2f}–{d['hi']:.2f} m."
        action='Verify route and approach conditions. Do not enter water to take photos.'
        bring='Equipment and crew must be confirmed by the incident commander.'
    else:
        situation='Visible apertures ranked by advisory void plausibility. Interior conditions unknown.'
        action='Structural assessment required. '+('; '.join(site['flags']) or 'Keep clear of damaged structures.')
        bring=f"Crew estimate: {site['crew']} (assumption); confirm equipment on site."
    deadline=site.get('time_to_critical_min')
    return dict(SITUATION=situation,DEADLINE=f'{deadline:.1f} min to context threshold (assumption)' if deadline is not None else 'No finite deadline computed',
                HAZARDS=', '.join(site.get('hazards',[])) or 'No hazard recorded; absence is not clearance',BRING=bring,ACTIONS=action,
                UNCERTAIN=('Mock/demo measurements are simulated. ' if site.get('simulated') else 'AI-selected references and rate assumptions require verification. ')+TEXT['footer'])
