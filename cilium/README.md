# Set up Minikube cluster

A local cluster with Minikube is the easiest solution for this demo, but the demo can also be following with any other cluster of your choice (e.g. GKE).

```sh
minikube start --network-plugin=cni --memory=4096
```

# Cilium

## Install Cilium CLI

Source: https://github.com/cilium/cilium-cli/

The CLI helps Kubernetes administrators interface with Cilium and manage it.

### Linux

```sh
export CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/master/stable.txt)
curl -L --remote-name-all https://github.com/cilium/cilium-cli/releases/download/${CLI_VERSION}/cilium-linux-amd64.tar.gz{,.sha256sum}
sha256sum --check cilium-linux-amd64.tar.gz.sha256sum
sudo tar xzvfC cilium-linux-amd64.tar.gz /usr/local/bin
rm cilium-linux-amd64.tar.gz{,.sha256sum}
```

### MacOS

```sh
export CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/master/stable.txt)
curl -L --remote-name-all https://github.com/cilium/cilium-cli/releases/download/${CLI_VERSION}/cilium-darwin-amd64.tar.gz{,.sha256sum}
shasum -a 256 -c cilium-darwin-amd64.tar.gz.sha256sum
sudo tar xzvfC cilium-darwin-amd64.tar.gz /usr/local/bin
rm cilium-darwin-amd64.tar.gz{,.sha256sum}
```

## A few Cilium CLI commands to try out

```sh
cilium version
cilium help
cilium status
cilium install --help
```

## Install Cilium in the Minikube cluster

Install Cilium:

```sh
cilium install
```

Then verify the installation:

```sh
cilium status
```

If you are curious about what happened under the hood, take a look at the pods:

```sh
kubectl get pods -A
```

Cilium is now properly installed and manages connectivity within the cluster.
To run a connectivity test (will be deployed in namespace `cilium-test`):

```sh
cilium connectivity test
```

Once done, clean up the connectivity test namespace:

```sh
kubectl delete ns cilium-test&
```

# Network Policies

Resources:
- https://kubernetes.io/docs/concepts/services-networking/network-policies/
- https://networkpolicy.io/
- https://networkpolicy.io/editor

One of the most basic CNI functions is the ability to enforce network policies and implement an in-cluster zero-trust container strategy.
Network policies are a default Kubernetes object for controlling network traffic, but a CNI such as Cilium is required to enforce them.
Let's deploy a very simple application to demonstrate how it works.

Inspect `simple-app.yaml`, then deploy it:

```sh
kubectl create -f simple-app.yaml
kubectl get all
```

In Kubernetes, all traffic is allowed by default. Check connectivity between pods:

```sh
FRONTEND=$(kubectl get pods -l app=frontend -o jsonpath='{.items[0].metadata.name}')
echo ${FRONTEND}
NOT_FRONTEND=$(kubectl get pods -l app=not-frontend -o jsonpath='{.items[0].metadata.name}')
echo ${NOT_FRONTEND}
kubectl exec -ti ${FRONTEND} -- curl -I --connect-timeout 5 backend:8080
kubectl exec -ti ${NOT_FRONTEND} -- curl -I --connect-timeout 5 backend:8080
```

Let's disallow traffic by applying a network policy. Inspect `backend-ingress-deny.yaml`, then deploy it:

```
kubectl create -f backend-ingress-deny.yaml
kubectl get netpol
```

And check that we traffic is now denied:

```sh
kubectl exec -ti ${FRONTEND} -- curl -I --connect-timeout 5 backend:8080
kubectl exec -ti ${NOT_FRONTEND} -- curl -I --connect-timeout 5 backend:8080
```

The empty network policy switched the default behavior from default allow to default deny.
Let's now selectively re-allow traffic again, but only from frontend to backend.

We could do it by crafting a new network policy manually, or we can also use the Network Policy Editor to help us out.

- Go to https://networkpolicy.io/editor.
- Upload our initial `backend-ingress.deny` policy.
- Rename the network policy to `backend-allow-ingress-frontend` (using the `Edit` button in the center).
- On the ingress side, add `app=frontend` as `podSelector` for pods in the same namespace.
- Inspect the network policy, then download it.

Then apply the new policy and check that connectivity has been restored, but only from the frontend:

```sh
kubectl create -f backend-allow-ingress-frontend.yaml
kubectl exec -ti ${FRONTEND} -- curl -I --connect-timeout 5 backend:8080
kubectl exec -ti ${NOT_FRONTEND} -- curl -I --connect-timeout 5 backend:8080
```

Not that we did not delete the previous deny policy:

```sh
kubectl get netpol
```

Network policies are additive.
Just like with firewalls, it is thus a good idea to have default `DENY` policies and then add more specific `ALLOW` policies as needed.

# Hubble

By default, Cilium acts as a regular CNI and only enhances networking (e.g. kube-proxy replacement) and somewhat helps with security (e.g. advanced network policies).
To take full advantage of eBPF deep observability and security capabilities, we must enable Hubble (which is disabled by default).

## Install the Hubble CLI

Source: https://github.com/cilium/hubble/

The Hubble CLI interfaces with Hubble and allows observing network traffic within Kubernetes.

### Linux

```sh
export HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)
curl -L --remote-name-all https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-linux-amd64.tar.gz{,.sha256sum}
sha256sum --check hubble-linux-amd64.tar.gz.sha256sum
sudo tar xzvfC hubble-linux-amd64.tar.gz /usr/local/bin
rm hubble-linux-amd64.tar.gz{,.sha256sum}
```

### MacOS

```sh
export HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)
curl -L --remote-name-all https://github.com/cilium/hubble/releases/download/$HUBBLE_VERSION/hubble-darwin-amd64.tar.gz{,.sha256sum}
shasum -a 256 -c hubble-darwin-amd64.tar.gz.sha256sum
sudo tar xzvfC hubble-darwin-amd64.tar.gz /usr/local/bin
rm hubble-darwin-amd64.tar.gz{,.sha256sum}
```

## A few Hubble CLI commands to try out

```sh
hubble version
hubble help
hubble observe --help
```

## Enable Hubble in Cilium

```sh
cilium hubble enable
```

Cilium agents will restart. We can wait for them to be ready by running:

```sh
cilium status --wait
```

Once ready, we can port-forward Hubble locally:

```sh
cilium hubble port-forward&
```

And then check Hubble status via the Hubble CLI:

```sh
hubble status
```

## Observing flows with Hubble

```sh
hubble observe
hubble observe -f
```

If we try to run spawn some network activity between our frontend and backend again, we might see it pop up in the feed:

```sh
for i in {1..10}; do
  kubectl exec -ti ${FRONTEND} -- curl -I --connect-timeout 5 backend:8080
  kubectl exec -ti ${NOT_FRONTEND} -- curl -I --connect-timeout 5 backend:8080
done
```

If we are interested in this traffic specifically, we can selectively filter it.
Some examples:

```sh
hubble observe --to-pod backend
hubble observe --namespace default --protocol tcp --port 8080
hubble observe --verdict DROPPED
```

Note that Hubble tells us the reason a packet was `DROPPED` (in our case, denied by network policy).
This is really handy when developing / debugging network policies.

## Hubble UI

Inspecting flows from the command line is nice, but how about seeing them in real time?
Let's reconfigure Hubble to enable Hubble UI:

```sh
cilium hubble enable --ui
cilium status --wait
hubble status
```

> Note: our earlier `cilium hubble port-forward` should still be running (can check by running `jobs` or `ps aux | grep "cilium hubble port-forward"`).
> If it does not, `hubble status` will fail and we have to run it again:
>
> ```sh
> cilium hubble port-forward&
> hubble status
> ```

To start Hubble UI:

```sh
cilium hubble ui
```

The browser should automatically open http://localhost:12000/ (open it manually if not).
We can then explore Hubble UI by selecting our `default` namespace, and then generating some network activity again:

```sh
for i in {1..10}; do
  kubectl exec -ti ${FRONTEND} -- curl -I --connect-timeout 5 backend:8080
  kubectl exec -ti ${NOT_FRONTEND} -- curl -I --connect-timeout 5 backend:8080
done
```

Hubble flows are displayed in real time at the bottom, and a visual graph of the activity is also displayed.
Click on any flow, and click on any property from the right side panel: notice that the filters at the top of the UI have been updated accordingly.

Let's run a connectivity test again and see what happens in Hubble UI:

```sh
cilium connectivity test
```

We can see that Hubble UI is not only capable of displaying flows within a namespace, it also helps visualizing flows going in or out.

# Encryption

Documentation: https://docs.cilium.io/en/stable/gettingstarted/encryption/

We're not going to showcase it in this demo but Cilium supports transparent encryption with IPsec and Wireguard.
If using the CLI for installing Cilium, enabling it is extremely simple:

```sh
cilium install --encryption ipsec
cilium install --encryption wireguard
```

# Clean up

```sh
minikube delete
```
