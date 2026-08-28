# Start in bootstrap mode.
# Terraform uses this to:
# - allow temporary public SSH access from the control node's current IPv4
# - generate the Ansible inventory using the VM's public IP
export TF_VAR_bootstrap_mode=true

# This script expects to be run from the project root so all relative paths resolve correctly.
# I am too lazy to figure out how to make it work no matter where you are located within the project directory

# Create/update the Azure infrastructure required for the bootstrap phase.
# Stop immediately if Terraform cannot establish the temporary public access path.
if ! terraform -chdir=./infra/terraform apply
then
  echo "Terraform Apply Denied"
  exit
fi

# Run the one-time bootstrap playbook over the VM's public interface.
# The playbook installs Tailscale, joins the VM to the tailnet,
# and prints the VM's Tailscale IPv4 address.
#
# Extract only that IPv4 address from the Ansible output and pass it
# back into Terraform as an input variable for the steady-state apply.
TF_VAR_tailscale_ip=$(
  ansible-playbook \
    -i ./ansible/inventory.yaml \
    ./ansible/playbook_boot.yaml |
  grep -oP '"msg":\s*"\K[0-9]{1,3}(\.[0-9]{1,3}){3}'
)

export TF_VAR_tailscale_ip

# Display the discovered Tailscale address so the bootstrap handoff is visible.
echo "Printing out the Tailscale IP that was found"
echo "${TF_VAR_tailscale_ip}"
echo "Done printing"

# Verify that the control node can actually reach the VM through Tailscale
# before removing the public SSH fallback.
#
# A DERP-relayed connection is acceptable here. We only need to prove
# that the private Tailscale path is working.
if ! tailscale ping --c=3 --until-direct=false "${TF_VAR_tailscale_ip}"
then
  echo "Ping Failed"
  echo "${TF_VAR_tailscale_ip} was not reachable via Tailscale. Exiting"
  exit
fi

# Add the VM's Tailscale address to SSH known_hosts so the next Ansible
# connection can use OpenSSH over Tailscale without an interactive
# host-authenticity prompt.
ssh-keyscan -H "${TF_VAR_tailscale_ip}" >> ~/.ssh/known_hosts

# Transition Terraform into steady-state mode.
#
# Terraform now:
# - removes the temporary public SSH ingress rule
# - stops depending on the control node's public IPv4
# - regenerates the Ansible inventory using the VM's Tailscale IP
export TF_VAR_bootstrap_mode=false

if ! terraform -chdir=./infra/terraform apply
then
  echo "Terraform steady-state apply failed"
  echo "Public bootstrap access may still be present. Review the Terraform plan/state before continuing."
  exit
fi

# Final smoke test:
# prove that Ansible can still manage the VM after public SSH has been removed.
# At this point the inventory points at the VM's Tailscale address, so this
# playbook should connect entirely through the private Tailscale network.
ansible-playbook \
  -i ./ansible/inventory.yaml \
  ./ansible/playbook_smoke.yaml











