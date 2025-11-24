import json
import os

def process_data():
    base_path = "data"
    device_file = [f for f in os.listdir(base_path) if f.startswith("xeronote-enhanced-devices")][0]
    plan_file = [f for f in os.listdir(base_path) if f.startswith("xeronote-enhanced-plans")][0]

    print(f"Processing {device_file}...")
    with open(os.path.join(base_path, device_file), 'r', encoding='utf-8') as f:
        devices = json.load(f)

    # Extract unique models
    # Structure: { "Galaxy S24": ["SM-S921", "S24", "갤S24"] } - approximated
    # The source has 'model_name' (Korean) and 'device_name' (Model Code)
    unique_models = {}
    for d in devices:
        m_name = d.get('model_name')
        d_name = d.get('device_name')
        if m_name and d_name:
            if m_name not in unique_models:
                unique_models[m_name] = set()
            unique_models[m_name].add(d_name)
    
    # Convert sets to lists
    final_models = []
    for m_name, d_names in unique_models.items():
        final_models.append({
            "name": m_name,
            "codes": list(d_names)
        })

    print(f"Found {len(final_models)} unique models.")

    print(f"Processing {plan_file}...")
    with open(os.path.join(base_path, plan_file), 'r', encoding='utf-8') as f:
        plans = json.load(f)

    unique_plans = set()
    for p in plans:
        p_name = p.get('plan_name')
        if p_name:
            unique_plans.add(p_name)
    
    print(f"Found {len(unique_plans)} unique plans.")

    output_data = {
        "models": final_models,
        "plans": sorted(list(unique_plans))
    }

    with open(os.path.join(base_path, "reference_db.json"), 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("Saved to data/reference_db.json")

if __name__ == "__main__":
    process_data()
